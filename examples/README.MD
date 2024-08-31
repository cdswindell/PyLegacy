# PyLegacy

This repository contains software to support Action 3.14; an organization
that focuses on electing scientists and engineers to political office. You can
learn more about them and their efforts at [314action.org]( https://314action.org).

Currently, code includes a Python-based interface to the Federal Election Commission
(FEC)'s [OpenFEC API](https://api.open.fec.gov). Through OpenFEC, a wealth of
demographic and financial data can be retrieved that is important to understanding
how candidates have performed historically.

Initial development focuses on the development of command-line tools (CLI) to
query specific financial data and return it in comma-separated-value (CSV) files that
can be imported into Excel and AirTable. Future work may include the development of
a website through which this data can be queried and downloaded in more consumable formats.

## Contents
- [Action 3.14]()
   - [Requirements](#Requirements)
   - [Installation and one-time setup](#installation-and-one-time-setup)
   - [Database Initialization](#database-initialization)
   - [Important Database Tables](#important-database-tables)
   - [CLI Scripts](#cli-scripts)
   - [Common Tasks](#common-tasks)

## Requirements

- Brew:

`/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`

- Python 3.11.2 (your version may be newer):
`brew install python@3.11`

- git:
`brew install git`

- gh:
`brew install gh`

## Installation and one time setup

```zsh
cd /where/you/like/source/

#Make sure this says 3.11.x or greater; don't keep going in these directions until it does
python3 --version

# authenticate gh/git:
gh auth login

#see: https://docs.python.org/3/library/venv.html
python3 -m venv legacyEnv
cd legacyEnv
gh repo clone cdswindell/legacyPy
cd legacyPy

# Activate virtual environment
source ../bin/activate; export PYTHONPATH=.

# Install 3rd-party dependencies
pip3 install -r requirements.txt

# customize your local environment
cp dev.env .env

# edit .env and substitute your API key for the default

```

You will need to activate this local python environment every time you open a
new shell, after cd'ing to the `314ActionPy` local directory by typing:

```
source ../bin/activate
export PYTHONPATH=.
```

You may wish to create a macro or alias to issue these commands for you.

## Database Initialization

The Web Application defined in this project requires a relational database to
store login credentials and user roles. We use Postgres V14 for this purpose.

Before running the web application on your local development environment, you
must create the local Postgres database used for authentication by
[flask-login](https://hackersandslackers.com/flask-login-user-authentication/).

Do so by typing:

```
createdb a314
```

Then add the required Postgres extensions:

```
psql a314
create extension pg_prewarm;
CREATE EXTENSION postgis;
CREATE EXTENSION fuzzystrmatch;
CREATE EXTENSION postgis_tiger_geocoder;
CREATE EXTENSION address_standardizer;
CREATE EXTENSION address_standardizer_data_us;
SELECT set_geocode_setting('use_pagc_address_parser', 'true');
quit
```
## Important Database Tables

The FEC maintains a vast, multi-terabyte data store of contributions to and expenditures from campaign committees and 
the candidate(s) they support. A subset of this data has been downloaded and is maintained in a series of 
`Postgresql` tables to enable 3.14 Action to identify potential democratic **STEM** candidates to recruit. The 
important tables are described below.

### Committees

The `committees` table contains unique records for the various campaign committees contributions are made to. Records 
are uniquely identified by a `committee_id`, assigned by the FEC. The `party` column contains the three-letter 
code for the political party, if provided, affiliated with the committee. For 
example, DEM for Democratic Party and REP for Republican Party. The`committee_candidate` table is used to 
associate campaign committees with candidates (See [candidates](#candidates)).

### Candidates

The `candidates` table contains unique records for the various candidates associated to a political committee 
(see [committees](#committees)). The table includes data on the candidate's associated political party as well as 
the state they are running in (for House and Senate elections), or if they are running for President (national office).
Records
are uniquely identified by a `candidate_id`, assigned by the FEC. The `committee_candidate` table is used to 
associate candidates with campaign committees (See [committees](#committees)).

### Stem Occupations
The `stem_occupations` table contains the names of occupations (jobs) considered to involve or require a **STEM** 
background. This table is used to identify records in the [contributions](#contributions) table to determine those 
made by individuals with **STEM** backgrounds via joining `stem_occupations` with [contributions](#contributions) 
on column `occupation`. Accordingly, matches are case-sensitive and exact. No fuzziness or other natural language 
processing is employed.

The `active` column in `stem_occupations` denotes if a given occupation record will be joined against the 
`occupation` column in the [contributions](#contributions) table.

As other **STEM**-related occupations are determined, they should be added to `stem_occupations`, and the jobs used 
to determine **STEM** contributors rerun. 

### Contributions

The `contributions` table contains records for every contribution made to a federal election campaign committee. 
These include contributions to House, Senate, and Presidential elections. It is important to note that contributions are 
made to a *campaign committee*; not directly to candidates themselves. The table includes the name, address, and 
occupation of the contributor, along with the date and amount of the donation, and the election cycle the donation 
occurred within. Election Cycles begin on an odd year and are named for their ending, even year, e.g., 2022, 2024.

A unique `row_id` is assigned to each record by the FEC. This column is used as the primary key for the table.

### Contributions Stem

The `contributions_stem` table is the subset of the records in [contributions](#contributions) table where the 
associated occupation is a one of the active occupations in the [stem_occupations](#stem-Occupations) table. 

The `normalized_address` column uses tools from the [PostGIS](https://postgis.net/docs/Extras.html) Postgresql 
extension to *normalize* the contributor street address information. This is necessary to identify unique 
contributors, as the FEC data is particularly noisy and dirty. The address normalizer uses data from the US Census 
(See [Tiger Mapping Files](https://www.census.gov/geographies/mapping-files.html)). This information is also used to 
help place contributors within state-wide legislative districts/

This table is updated by the stored procedure [update_contributions_stem](#update-contributions-stem).

## CLI Scripts

The `CLI` directory contains a number of Python command line scripts allowing 
you to query and interact with the FEC database. As a prerequisite, you must 
have obtained a valid FEC API Key and

## Common Tasks
### Refresh Committees Table
