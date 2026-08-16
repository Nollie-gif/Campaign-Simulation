# License scope

Campaign-Simulation is meant to be used, changed, studied, broken, repaired, forked, and improved.

That is not accidental wording. The reusable framework exists because the useful parts of the private experiment were worth separating from the campaign that produced them.

## What the MIT License covers

The repository-level [MIT License](LICENSE) applies to the original Campaign-Simulation software and original framework documentation in this repository, including the reusable source code, schemas, templates, tests, technical contracts, and campaign-neutral documentation, except where a file or directory explicitly says otherwise.

You may use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of that MIT-licensed material under the terms of the MIT License.

## What it does not cover

The MIT License does **not** grant rights to third-party intellectual property merely because that material appears in this repository.

In particular, the historical files under [`artifacts/`](artifacts/) are deliberately preserved development fossils. Some include fan-created material based on or referring to intellectual property owned by Wizards of the Coast and/or other third parties. Those artifacts are outside the repository's MIT software-license grant and are governed by the notices in [`artifacts/RIGHTS.md`](artifacts/RIGHTS.md), applicable third-party rights, and any relevant fan-content policies.

Nothing in this repository is intended to relicense Wizards of the Coast material, trademarks, artwork, published rules text, or other third-party content.

## Why the split exists

The framework is the reusable thing.

The artifacts are the receipts.

We want people to be able to take the architecture and build with it without pretending that a historical campaign document and a piece of reusable software are legally the same object. They are not, and squashing them together would make the repository simpler only in the way hiding cables under a rug makes a room simpler.

If a future contribution introduces third-party material, that material must be identified and scoped before it is treated as MIT-licensed repository content.
