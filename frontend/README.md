# Technical Reporting Web

Angular client for the Royal Tyres technical-reporting platform.

## Commands

```bash
npm install
npm start
npm test -- --watch=false
npm run build
```

The application is organised by lazy-loaded business features. Cross-cutting authentication, layout and persistence services live under `src/app/core`; reusable models live under `src/app/shared`.
