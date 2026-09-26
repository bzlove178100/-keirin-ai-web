# Credential-gated provider action boundary

`agent_core.credential_adapter` connects the existing `CredentialProvider` abstraction to
provider actions without giving runners/adapters direct access to refresh secrets.

This is a code-only boundary. It does **not** bind a real provider, secret store, hosted
worker, scheduler or production execution path.

## Execution order

For every wrapped adapter action:

1. validate that a `CredentialRequirement` exists for the exact action;
2. request an access-only `CredentialSnapshot` from the configured provider;
3. require the configured capability scope / TTL / known-expiry policy;
4. if credential acquisition fails, raise a fixed `BlockedAction` **before the
   underlying provider action is invoked**;
5. inject the access snapshot only into the local in-memory action context;
6. invoke the underlying action;
7. reject results that attempt to return a `CredentialSnapshot` object.

The snapshot is never written into TaskSpec, step args, checkpoint state or activity
payloads by the wrapper.

## Fail-closed task behavior

`AgentRunner` persists the step attempt before calling an action. Therefore a credential
failure is recorded as a terminal `blocked` task even though the underlying provider
action was never invoked.

This is intentional. Authentication repair does not automatically retry the task.
A later recovery procedure must explicitly prove that no provider action occurred and
reconcile the task before a retry is permitted.

Credential-provider exceptions are classified inside their handler, but the fixed
`BlockedAction` is raised only after leaving that handler. This prevents provider-specific
exception text (which might contain credentials) from being retained as outward Python
exception context and then persisted by the runner.

## Provider adapter responsibility

The underlying provider adapter accesses its snapshot with:

```python
snapshot = require_credential_snapshot(context)
token = snapshot.secret("access_token")
```

The provider adapter remains responsible for:

- placing the access token only in provider authentication headers/transport state;
- never returning the token as action data, artifacts, messages or errors;
- using the requested provider/account/capability identity;
- respecting its registered read/write/execute capability classification;
- bounded provider I/O and deterministic verification.

The generic wrapper detects an actual `CredentialSnapshot` object in nested return
values, but it cannot infer that an arbitrary returned string is a token. Secret-value
redaction therefore remains a provider-adapter contract as well as a credential-provider
contract.

## Requirement coverage

Credential requirements must cover every action exposed by the wrapped adapter, including
verification actions. Partial coverage fails adapter construction rather than leaving an
unguarded provider action available.

A requirement includes:

- exact action name;
- required credential capabilities;
- minimum TTL;
- whether expiry must be known.

The wrapper preserves the adapter's normal `Capability` metadata, so the existing
`ToolRegistry` access-class checks remain in force independently from credential scope.

## Not activated by this module

This module does not:

- enable hosted task execution;
- configure a refresh-secret store;
- perform a real token refresh;
- grant provider permissions;
- start a worker/scheduler/recurrence loop;
- enable GitHub writes;
- enable production prediction or keirin prediction DB writes;
- enable automatic keirin race-data collection;
- enable generation-provider execution;
- deliver the 21:00 report.

A concrete live provider binding remains a separate authorization/integration boundary.
