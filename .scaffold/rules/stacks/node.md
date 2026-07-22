# Node.js Stack Rules

## Build & Test

- Check `package.json` for scripts: `npm test`, `npm run build`, `npm run lint`
- Detect package manager from lock files: `package-lock.json` (npm), `yarn.lock` (yarn), `pnpm-lock.yaml` (pnpm)
- Use the detected package manager consistently

## Conventions

- Follow existing module format (ESM vs CJS) as established
- Match existing code style (semicolons, quotes, etc.)
- Prefer `const` over `let`, never use `var`

## Safe Commands

npm test, npm run build, npm run lint, npm install, npx, node, yarn test, yarn build, pnpm test, pnpm build
