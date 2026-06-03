# HACS default repository submission

After tagging a stable release of `Shaffer-Softworks/biamp-tesira`:

1. Fork [hacs/default](https://github.com/hacs/default) (or use the `sickkick/HACS` fork pattern from other Shaffer-Softworks integrations).
2. Add `"Shaffer-Softworks/biamp-tesira"` to the `integration` JSON array in **alphabetical** order.
3. Ensure `custom_components/biamp_tesira/brand/` contains icon assets (HA 2026.3+).
4. Open a PR against `hacs/default` `master` with validation `ignore: brands` if required.
5. Mark the PR ready for review after CI passes.

See [hacs-default-pr.mdc](/Users/michaelshaffer/.cursor/rules/hacs-default-pr.mdc) for prior Shaffer-Softworks examples.
