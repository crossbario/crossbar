# Contributing to Crossbar.io

:+1::tada: First off, thanks for taking the time to contribute! :tada::+1:

Contributing to Crossbar.io is totally welcome! We love open source and community collaboration. All of Crossbar.io development is fully open here on GitHub and there are no private, closed areas that exclude you and the Crossbar.io community.

The guidelines here give some tips on how to best contribute. Please try to follow these. It's short, quick and easy. This will ensure a smooth process. Thanks again for contributing!

**Quick Links**

* [Filing Bugs](#filing-bugs)
* [Filing Features](#filing-features)
* [Asking Questions](#asking-questions)
* [Contributing Code](#contributing-code)
* [Contributing Documentation](#contributing-documentation)

## Filing Issues

We track **issues** in the GitHub issue tracker [here](https://github.com/crossbario/crossbar/issues).

An issue is either a **bug** (an unexpected / unwanted behavior of the software or incorrect documentation) or a **feature** (a desire for new functionality / behavior in the software or new documentation).

A **question** though is *not* an issue - as in, it isn't handled in our issue tracker by purpose / policy.

So if you have found a bug or want to propose a new feature, please file an issue. But if you have a question, please see [Asking Questions](#Asking Questions)

### Filing Bugs

If you file a **bug issue**, please provide at least the following information:

1. output of `crossbar version`
2. error/log output (eg a traceback)
3. steps to reproduce the issue

> A bug issue should also be only about **one thing** - if you have found multiple related things, please file multiple issues and link the issues (cross referencing by mentioning the related issues in the descriptions - that will make GitHub automatically add respective links).

### Filing Features

When proposing a new **feature**, please provide the following:

1. your actual **use case** and your **goals**
2. *why* this important for you
3. optionally, a proposed solution

> Describing your use case and goals, rather than only / directly jumping into a specific, concrete proposal for a solution is very important. As this allows us to take into account the bigger picture. If you "only" propose concrete solution, and that doesn't fit in, we might need to reverse engineer your actualy use case / goals first to then come up with a solution that fits.

### Asking Questions

A question about Crossbar.io is neither a bug nor a feature. **Hence, if you have a question, please DO NOT file an issue, but consider asking on one of the following channels.**

Questions are best asked here:

* on the [mailing list](https://groups.google.com/forum/#!forum/crossbario)
* on [StackOverflow](http://stackoverflow.com/questions/ask?tags=crossbar,wamp) or
* on IRC channels (`#autobahn` and `#crossbar` at `chat.freenode.net`).

> When you file an issue that is considered a mere question, your issue likely will get closed without any further discussion or reply. You might find that unpleasant or non-cooperative. We are sorry! It is meant to be rude, but the reasons are: a) we are running this project on limited resources and b) the issue tracker should stay focused and not drown in noise.

## Contributing Code

1. All development happens on GitHub and we use the usual fork the repository, branch-per-issue, [pull request](https://help.github.com/articles/using-pull-requests) and merge workflow, also known as [GitHub Flow](https://guides.github.com/introduction/flow/).
2. A necessary **requirement** is that an issue needs to exist first. That is, a PR is always for a specific issue. The branch should be name like this: `<descriptive_name>_issue<NNN>`.
3. Another prerequisite (for merging code) is that you have [signed and sent us a contributor agreement](#send-us-a-contributor-assignment-agreement). This only needs to be done once, but we cannot merge code until we have received a CAA.
4. Further, we have a CI system in place running the whole set of unit tests for Crossbar.io on various platforms. The CI system will be triggered automatically when you do a PR. A necessary condition for a PR to be merged that all of our tests run green.
5. An issue branch from a PR must be rebased to the **master** branch before merging. We don't have a policy (currently) regarding squashing - that is, you can leave your commits or squash them, but rebasing is necessary.
6. If your branch doesn't run green on our CI, or your branch becomes stale, because other things were merged in between, you are responsible for fixing thing on your branch first.

### Fork us on GitHub

We use the Fork & Pull Model. This means that you fork the repo, make changes to your fork, and then make a pull request here on the main repo.

> This [article on GitHub](https://help.github.com/articles/using-pull-requests) gives more detailed information on how the process works.

### Send us a Contributor Assignment Agreement

Before you can contribute any changes to the Crossbar.io project, we need a CAA (Contributor Assignment Agreement) from you.

The CAA gives us the rights to your code, which we need e.g. to react to license violations by others, for possible future license changes and for dual-licensing of the code. The CAA closely follows a template established by the [Harmony project](http://harmonyagreements.org/), and CAAs are required by almost all open source projects which are non-trivial in scope.

#### What we need you to do

1. Download the [Individual CAA (PDF)](https://github.com/crossbario/crossbar/raw/master/legal/individual_caa.pdf).
2. Fill in the required information that identifies you and sign the CAA.
3. Scan the CAA to PNG, JPG or TIFF, or take a photo of the box on page 2 (the **entire box**, including the information identifying the document).
4. Email the scan or photo to `contact@crossbario.com` with the subject line "Crossbar.io project contributor assignment agreement"

*If your write contributions as part of your work for a company, you also need to send us a [Entity CAA (PDF)](https://github.com/crossbario/crossbar/raw/master/legal/entity_caa.pdf) signed by somebody responsible in the company.*

**You only need to do this once - all future contributions are covered!**

> We are looking into a fully electronic workflow to get legally binding CAAs, but due to how different legislations handle electronic signing, we currently see no other way than the print/scan/mail workflow. Sorry for the inconvenience! For a detailed explanation of what the CAA means for you, and why we need it, see the [CAA FAQ](FAQ Contributor Assignment Agreement).

## Contributing Documentation

Contributions to the documentation are highly welcome! Crossbar.io is a complex software, users have varying degrees of background and experience and we have limited resources. Also, developers of Crossbar.io usually don't have a **user perspective** (anymore) - but docs should be for users.

All Crossbar.io documention is written in (enriched) [Markdown](https://en.wikipedia.org/wiki/Markdown) and contained in this repository [here](https://github.com/crossbario/crossbar/tree/master/docs).

The documentation is the built (by us) and deployed [here](http://crossbar.io/docs/).

For further details, please see [here](https://github.com/crossbario/crossbar/tree/master/docs/README.md).
