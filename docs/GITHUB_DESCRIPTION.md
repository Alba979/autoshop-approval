# GitHub Upload Info

Use this when you create the repository on GitHub.

## Suggested repo name

`autoshop-approval-workflow`

## Short description (for the GitHub "About" field)

Small-shop web app that enforces explicit customer approval before repair
work begins: technicians log diagnostics and estimates, customers approve
or decline over a one-tap SMS link, jobs auto-hold/expire if unanswered,
and every diagnostic photo and approval timestamp is retained for warranty
disputes - plus a per-technician analytics dashboard.

## Suggested topics

`flask` `python` `small-business` `auto-repair` `sms-approval` `sqlalchemy`
`workflow-automation` `shop-management` `twilio` `bootstrap`

## Longer description (for the repo README top / release notes / portfolio writeup)

Ridgeline Auto Repair's diagnostic-to-repair approval workflow is a
production-ready Flask application built for a single independent auto
shop. It replaces phone-call-and-sticky-note repair approvals with an
auditable system: a technician logs what they found (with photos), builds
an itemized parts/labor estimate, and the system texts the customer a
one-tap approve/decline link. Estimates that exceed a customer's
spending cap always require a fresh, explicit approval - never a
carried-over "yes" from a smaller job. Jobs that go unanswered
automatically move to a "waiting on customer" hold and expire on a
configurable timeout. Every diagnostic photo and every approval
request's sent/response timestamps are permanently retained for warranty
recordkeeping. An analytics dashboard tracks average approval turnaround
time and estimate-to-final-cost variance per technician.

Ships with realistic seed data (multiple technicians, customers, and
jobs spanning every stage of the workflow), a full pytest suite covering
the spending-cap and timeout logic, Docker/Compose for deployment, and a
deployment guide covering the path from SQLite + local disk to Postgres
+ S3 as a shop grows.

## Notes

This codebase was written from scratch for this project brief and does not
copy or derive from any existing open-source shop-management repository.
