## Upgrading with Git [source][]

[source]: https://github.com/chrisdaaz/coldfront/blob/21c66b81575a8387a59651a30e46c5f6c7909197/docs/pages/upgrading.md

This is one way to use Git to upgrade your codebase with the latest upstream changes in ColdFront. 

Git Remote setup:

- `origin` -> Your organization's Git repo for ColdFront
- `upstream` -> https://github.com/coldfront/coldfront.git 

Git Branch setup:

- `custom` -> This is your default branch, containing your organization's ColdFront codebase
- `main` -> This branch tracks the `main` branch of the ColdFront project
- `staged_upgrade` -> This is based on your `custom` branch, used for resolving merge conflicts


***Set up the local repo with appropriate branches and remotes:***

Clone the original repo and create up your local "custom" branch:

    git clone https://github.com/coldfront/coldfront.git
    cd coldfront
    git checkout -b custom v1.1.7

Set up your own remote:

    git remote remove origin
    git remote add origin <your remote>
    git push -u origin/custom custom

(You may also want to set the 'default' branch on your git host to 'custom'.)

Set up the `upstream` remote; `main` tracks the `upstream` remote:

    git remote add upstream 
    git branch --set-upstream-to upstream/main main

For dev work, be sure you start from `custom` and then create a new branch:

    git switch custom
    git switch -c feat/plugin


***Example commands from [source][]:***

```sh
# let's assume you only have a `main` branch and a `custom` branch
git checkout main
# pull in the latest changes
git pull upstream main

# return to your custom branch
git checkout custom
# make a new branch off of your `custom` branch
git checkout -b staged_upgrade
git merge main

# alternative: checkout a tagged release instead of using `main`
# git fetch --all --tags
# git tag -l
# git merge v1.x.x

# Install any updated dependencies
uv sync

# resolve any conflicts in your text editor
git commit -m "bring in latest changes"
```

Migrate your database to accomodate changes to models:

```sh
uv run coldfront makemigrations --merge
uv run coldfront migrate
```

Restart your server in your testing environment to confirm everything is working as expected. If everything looks good, merge your `staged_upgrade` branch into your default branch:

```sh
git checkout custom
git merge staged_upgrade
# update your remote
git push origin custom
git branch -d staged_upgrade
```

Your organization's ColdFront codebase should now have the latest updates from the upstream ColdFront project.

