FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --legacy-peer-deps

COPY . .

EXPOSE 5173

# Dev server, not a production build: this container exists so a reviewer
# can `docker compose up` and see the app working end-to-end in one command.
# A production image would instead run `npm run build` behind nginx/Caddy.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
