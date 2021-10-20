MeDB
====

MeDB is a Python Flask application designed to help you own your data. Actually,
it's an application designed to help *me* own *my* data.

The goal of this project is to create a self-hosted web application that allows
the following:

- Modules can import, store, and display data about me.
- Modules can ask me to help maintain this data, e.g. by annotating it or
  entering it in.
- Modules allow easy export of all data to useful formats, such as CSV or Google
  Sheets, with no additional effort.
- The application presents a well-documented SQL database which can be queried
  in a standard Python data analysis stack (Pandas, Matplotlib, etc)
- The application exposes a Jupyter hub implementation which allows me to do
  interactive data analysis, publish notebooks, and schedule their execution
  (stretch).

Modules
-------

To understand this project better, here are some planned or implemented modules:

### Shiso

_Status: in development_

Shiso is like Mint, but better! Shiso will use the Plaid financial information
API to load my transaction data. Rather than the ad-laden, cookie-cutter
experience that Intuit Mint presents, it will give me an ad-free, customized
interface to the information I want to see:

1. All transactions get *reviewed by me* within a few days! Reviewing includes
   verifying that I recognize the transaction, assigning a category suitable for
   my budget strategy, and assigning a split strategy if appropriate. The
   transaction review process is designed to be fast for the average cases and
   simple to start. If I haven't reviewed recently, email/push will notify me.

2. Splitting that makes sense. Shiso will allow me to save custom split
   strategies (e.g. roommates, significant other, etc), and quickly apply them
   as I review strategies. Split strategies can designate whether split line
   items should apply to budgets, or not.

3. Category rules can easily be added and improved, to speed up transaction
   review. Category trees will follow a simple namespace structure such as
   `entertainment.streaming` or `food.groceries`.

4. Subscription purchases can be recorded and included in budgets. New
   subscriptions can be guessed based on transaction data.

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


Design
------

Some core parts of the design:

- Minimize Javascript use as much as possible. MeDB is not a SPA. Each page is
  rendered via Jinja templating, and each interaction involves a page load.
  That's ok!

  The reasoning here is not that JS is bad. I'm not very good with JS, and to be
  honest, this project is about playing to my strengths and making it easy for
  me to quickly build interfaces and data analyses.

- Design schemas which would be useful to query via raw SQL.

- Make the user do _as little work as possible!_

- Don't implement more than you need to.

Development
-----------

1. Make sure configuration is in place at `.env` and `.env.secret`.
2. `python -m venv venv`
3. `. venv/bin/activate`
4. `pip install wheel python-lsp-server` (omit lsp server for non-dev)
5. `pip install -r requirements.txt`
6. `flask user setup`
7. `flask run`
