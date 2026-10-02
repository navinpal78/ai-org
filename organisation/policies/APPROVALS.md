# Approvals

## Purpose

This policy defines operational approval levels for organisational work.

The CEO Constitution remains authoritative if a conflict exists.

## GREEN — Autonomous

Examples:

- research;
- analysis;
- planning;
- drafting;
- documentation;
- code inspection;
- non-destructive testing;
- simulations;
- organisational analysis;
- registry design;
- non-destructive validation;
- preparing implementation plans;
- approved foundation documentation work.

GREEN authority does not permit actions that are classified as YELLOW or RED.

## YELLOW — Owner Approval Required

Examples:

- software installation;
- significant configuration changes;
- database migrations;
- infrastructure changes;
- network changes;
- permission changes;
- new external services;
- website deployment;
- production configuration;
- creation or activation of a new operational agent where approval is
  required;
- changes with meaningful operational impact.

The CEO must obtain approval before execution.

## RED — Explicit Owner Authority Required

Examples:

- deletion of important organisational data;
- destructive database migrations;
- major firewall changes;
- shutdown of important systems;
- significant production changes;
- irreversible operations;
- significant external spending;
- exposing previously private systems;
- transferring sensitive information externally;
- actions with substantial or irreversible external consequences.

## Read-Only

READ-ONLY is a task authority state, not an approval level.

When a task is explicitly READ-ONLY:

- no filesystem writes;
- no configuration changes;
- no installations;
- no agent creation;
- no registry changes;
- no commits;
- no persistent reports.

The result must be returned to the requesting Owner or controlling system without
persistent modification unless a separate write authority is granted.

## Approval Record

Approval records should capture:

- date/time;
- requester;
- action;
- reason;
- authority level;
- approving authority;
- scope;
- result;
- relevant files or systems;
- verification.

## Current State

No operational approvals are assumed merely because a policy or ROLE.md
exists.
