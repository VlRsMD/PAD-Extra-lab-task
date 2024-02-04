FROM node:14

WORKDIR /usr/src/app

COPY package*.json ./

RUN npm install

COPY . .

EXPOSE 7000

ENV CI=true

CMD ["node", "gateway.mjs"]