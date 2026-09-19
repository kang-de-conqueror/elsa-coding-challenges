import { chromium } from 'playwright-core'

// Usage: server on :8000, client on :5173, then `npm run test:e2e`.
// E2E_CHANNEL picks the installed browser (chrome | msedge), default chrome.
const APP = process.env.E2E_URL ?? 'http://localhost:5173/'
const room = `e2e-${Date.now()}`
const log = (...a) => console.log(...a)
const fail = (m) => { console.error('FAIL:', m); process.exitCode = 1 }
const check = (cond, m) => {
  if (cond) log('ok  -', m)
  else fail(m)
}

const browser = await chromium.launch({ channel: process.env.E2E_CHANNEL ?? 'chrome', headless: true })
// One browser context => both tabs share localStorage; the session lives in sessionStorage (per tab).
const ctx = await browser.newContext()
const consoleErrors = []
async function tab(name) {
  const p = await ctx.newPage()
  p.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(`${name}: ${m.text()}`)
  })
  p.on('pageerror', (e) => consoleErrors.push(`${name}: ${e.message}`))
  return p
}
const alice = await tab('alice')
const bob = await tab('bob')

async function join(page, name) {
  await page.goto(APP)
  await page.getByLabel('Quiz ID').fill(room)
  await page.getByLabel('Your name').fill(name)
  await page.getByRole('button', { name: 'Join quiz' }).click()
  await page.getByText('Waiting for players').waitFor({ timeout: 10000 })
}

await join(alice, 'alice')
await join(bob, 'bob')
check(await alice.getByText('bob').isVisible(), 'alice sees bob in the lobby (two tabs, same browser, distinct users)')
check(await bob.getByText('alice').isVisible(), 'bob sees alice in the lobby')
check((await alice.getByText('Connected').count()) > 0, 'connection status shows Connected')

await alice.getByRole('button', { name: 'Start quiz' }).click()
await alice.getByText('Question 1 / 5').waitFor({ timeout: 10000 })
await bob.getByText('Question 1 / 5').waitFor({ timeout: 10000 })
check(true, 'both tabs receive question 1')

// q1 correct answer is "Joyful"; bob answers wrong on purpose
await alice.getByRole('button', { name: 'Joyful' }).click()
await bob.getByRole('button', { name: 'Sad' }).click()
await alice.getByText(/Correct! \+\d+ points/).waitFor({ timeout: 5000 })
await bob.getByText('Incorrect').waitFor({ timeout: 5000 })
check(true, 'alice sees Correct!, bob sees Incorrect')
check(await alice.getByRole('button', { name: 'Sad' }).isDisabled(), 'choices are locked after answering')

await alice.locator('.leaderboard li').first().waitFor({ timeout: 5000 })
await alice.waitForFunction(() => document.querySelector('.leaderboard li .name')?.textContent === 'alice', null, { timeout: 5000 })
check(true, 'leaderboard ranks alice first, live')
await bob.waitForFunction(() => document.querySelector('.leaderboard li .name')?.textContent === 'alice', null, { timeout: 5000 })
check(true, 'bob sees the same live leaderboard')

// reload alice mid-quiz: session survives in sessionStorage, page resumes the same user
await alice.goto(`${APP}?quiz=${encodeURIComponent(room)}`)
await alice.getByText('Question 1 / 5').waitFor({ timeout: 10000 })
check(await alice.getByText(/Correct! \+\d+ points/).isVisible(), 'after reload alice resumes: same question, her earlier result restored')
check(await alice.getByRole('button', { name: 'Sad' }).isDisabled(), 'and cannot answer the question twice')

// finish the whole quiz (5 x 15s) and check the end screen
await alice.getByText('Final results').waitFor({ timeout: 100000 })
await bob.getByText('Final results').waitFor({ timeout: 20000 })
const names = await alice.locator('.leaderboard li .name').allTextContents()
check(names[0] === 'alice' && names[1] === 'bob', `final standings alice > bob (${names.join(', ')})`)

check(consoleErrors.length === 0, `no browser console errors ${consoleErrors.join(' | ')}`)
await browser.close()
