MeDB
====

MeDB is an application designed to help me store and manage my own data. It is a
self-hosted web application with modules that manage particular kinds of data,
such as finance or fitness tracking data.  The data is simply stored in sqlite.
I self-host the application in a VPN for security (because I'm not optimistic
about my web application security abilities).

The idea is that I'll be able own my own data, write my own code that solves my
particular problems, graph my own data, and more. In the future, ideally MeDB
would even embed a Jupyter notebook for me to do ad-hoc analysis.

Modules
-------

To understand this project better, here are some planned or implemented modules:

### Shiso

_Status: quite usable, and adding new features_

Shiso is like Mint, but better! Shiso uses the Plaid financial information API
to load my transaction data. Rather than the ad-laden, cookie-cutter experience
that Intuit Mint presents, it has a simple, lightweight, and ad-free interface.
Here are some major features:

1. All transactions get *reviewed by me* within a few days! Reviewing includes
   verifying that I recognize the transaction, assigning a category suitable for
   my budget strategy, and assigning a split strategy if appropriate. The
   transaction review process is designed to be fast for the average cases and
   simple to start. In the future, I'll setup email reminders to review new
   transactions every so often.

2. Splitting that is quick and easy to use. I frequently pay for things that
   will later be split. Shiso has easy options that specify no split, half
   split, fully reimbursed, or some other value. Currently Shiso supports only
   one other payer, but I may extend it.

3. Simpler categories. Right now, I have a smaller list. But in the future, I'd
   like to spend some time on a category ontology (which is hierarchical, yeah!)
   and some automatic rules to take a first guess.

Most importantly, I'll be able to improve any feature or write any analysis I'd
like for my finances.

### Fit

_Status: planned_

My current set of fitness applications involves some duplication. I'd like to
create an interface which can allow me to enter common data (daily weight,
daily exercises) and synchronize it across services. Then, I'd like to be able
to pull any data which I enter into those services (e.g. food logging or
activity tracker data, sleep time, etc) and store it to my own service.

This service will not have an extensive UI, but will feature a data model and be
pretty useful for querying information.

### Speedtest

_Status: basic implementation_

Runs a speedtest each hour and stores the result in a database. View the results
via matplotlib and d3.js!

Development
-----------

1. Make sure configuration is in place at `.env` and `.env.secret`.
2. `python -m venv venv`
3. `. venv/bin/activate`
4. `pip install wheel python-lsp-server` (omit lsp server for non-dev)
5. `pip install -r requirements.txt`
6. `flask user setup`
7. `flask run`

For testing tasks, you'll want to concurrently run:

```
venv/bin/celery -A autoapp.celery worker -l INFO
```

The development configs use sqlite as a broker, so you don't need much additional setup.
