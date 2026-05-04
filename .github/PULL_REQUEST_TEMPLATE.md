# Pull Request

Private Hodler Suite UAB repository. Do not include customer data, credentials,
private URLs, secrets, or confidential business context beyond what reviewers
need.

## Summary

- <!-- Describe the change in 1-3 bullets. -->

## Change Type

- [ ] Fix
- [ ] Feature
- [ ] Refactor
- [ ] Docs
- [ ] Test
- [ ] CI / Deploy

## Scope

- [ ] `scripts/v2.8` app/risk/GitOps path
- [ ] `scripts/v2.0/web_portal` manual web portal path
- [ ] `.github` workflows or repo automation
- [ ] Documentation only
- [ ] Other:

## Testing

Commands run:

```bash

```

## Security / Data Handling

- [ ] No `.env`, private keys, SQLite databases, logs, or raw runtime caches are included.
- [ ] User/customer data, tokens, webhook URLs, cookies, and signed URLs are not exposed.
- [ ] Auth, billing, webhook, upload, Slack/email, or data-retention changes were reviewed carefully.
- [ ] The change does not disclose Hodler Suite UAB proprietary implementation details outside this private repository.
- [ ] Not applicable.

## Deployment / Rollback

- Deployment path:
  - [ ] GitHub Actions auto-deploy (`scripts/v2.8`)
  - [ ] Manual web portal deploy (`scripts/v2.0/web_portal`)
  - [ ] No deploy required

Rollback notes:

- <!-- How should this be reverted or rolled back if needed? -->

## Screenshots

Add screenshots for UI changes, or write `N/A`.

## Linked Issues

Fixes #
