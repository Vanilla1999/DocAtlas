#!/usr/bin/env python3
"""Real installed-artifact stdio delivery smoke; no mocked retrieval or providers.

Full smoke prepares a cold host-selected member store through confirmed MCP,
then retrieves and repeats preparation after restart. Local library fixtures
are preloaded separately after cold preparation and never count as lifecycle
acceptance. --read-only checks cold rejection without provisioning storage.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import url2pathname

from docmancer.mcp.agent_config import AgentTarget, register_server

TOOLS = {"get_docs_context", "prepare_docs", "docs_status"}
QUESTION = "Which command starts the Docs MCP server?"
NEEDLE = "doc-atlas mcp docs-serve"
LARGE_PHASES = ("LeaseAcquire", "LeaseRenew", "CheckpointCommit", "LeaseRelease", "CrashRecover")
LARGE_QUESTION = (
    "Implement the coordinator using the documented constraints for "
    + ", ".join(f"`{phase}`" for phase in LARGE_PHASES)
    + ". Preserve the lease, ledger, payload, acknowledgement and reconciliation conditions, "
    "including their failure cases and retry rules."
)


def natural_protocol_documents() -> dict[str, str]:
    """Authored independent subsystem contracts; no length-driven generation.

    Two policy paragraphs per phase describe distinct obligations. Default
    indexing alone determines their children; these strings are not chunks.
    """
    return {
        "docs/leases.md": """# Lease ownership

## Acquisition

During `LeaseAcquire`, the lease manager must allocate an epoch greater than every epoch previously committed for the partition. The allocation and owner record belong to one transaction; a worker may not announce ownership while that transaction is pending. A failed comparison against the previous owner is a normal contention result, not permission to overwrite the winner. The proposed deadline uses the manager's monotonic clock and is stored with the epoch, partition and worker incarnation. Reusing a process identifier after restart must not reuse an incarnation. The caller receives a lease only after the durable owner record can be read back through the same partition routing decision. An unavailable routing entry leaves acquisition pending and must not select another partition silently.

A `LeaseAcquire` request also carries the caller's expected routing revision. The manager must reject a revision older than the partition's current assignment, even if the lease appears expired, because an expired worker can still have delayed requests in flight. Before admitting a new owner, install its fencing epoch in the payload store and ledger; both acknowledgements must name the same partition and epoch. If only one acknowledgement arrives, retain the provisional owner without granting write access. Recovery can resume these acknowledgements using the acquisition identifier. It must never solve a half-installed fence by lowering either subsystem's epoch. Administrative reassignment uses this same transition and records the previous owner for later reconciliation.

## Renewal

For `LeaseRenew`, compare the complete owner tuple, including incarnation and fencing epoch, before extending the deadline. A heartbeat containing only a worker name is insufficient. Renewals may advance a deadline but must never reduce it or revive a superseded epoch. The manager must evaluate expiration using its own clock rather than accepting a client timestamp as current time. A queued renewal that arrives after ownership changed receives a terminal stale-owner response. The worker then stops starting new writes and marks its unfinished requests for reconciliation. It may finish reading the result of a previously committed operation, provided that read cannot create another acknowledgement or modify the lease. Renewal success must identify the resulting deadline explicitly.

The `LeaseRenew` retry identifier is bound to the requested extension and the original owner tuple. An identical retry returns the previously committed deadline without extending it again. Reusing that identifier with a different extension is a conflict, not a request to choose the larger value. If the renewal response is lost, the worker may ask for the recorded outcome while its old deadline remains valid; it cannot assume success from a socket timeout. Once the old deadline expires, new work waits for a confirmed outcome or a fresh acquisition. The manager must retain renewal outcomes until the associated incarnation is fenced out and reconciliation has consumed its outstanding ledger entries, so delayed retry messages cannot accidentally receive a new effect.

## Checkpoint

At `CheckpointCommit`, lease ownership is checked again inside the transaction that publishes the checkpoint pointer. A lease observed at request admission is not sufficient for a later commit. The comparison includes the epoch carried by every payload descriptor in the checkpoint. Mixing descriptors from two epochs must fail even when both were written by a worker with the same display name. The checkpoint transaction records which lease deadline was observed, but that timestamp is diagnostic and cannot replace the epoch comparison. If the lease expires before publication, the worker leaves prepared payloads invisible and records a recoverable pending outcome. It must not publish an incomplete checkpoint merely to finish before its process exits.

The `CheckpointCommit` publication boundary establishes which operations survive an ownership change. Once the checkpoint pointer commits under the correct epoch, a later owner must preserve that checkpoint even if its original worker never received success. Before the pointer commits, ownership loss prevents publication and permits recovery to classify the prepared payloads as unattached. A manager must not erase a committed pointer when fencing the previous worker. Instead, the successor reads the pointer and verifies its ledger transaction before processing new requests. This rule applies equally to graceful handover and expiration. A checkpoint with a newer valid sequence is never replaced by an older sequence recovered from a delayed worker response.

## Release

During `LeaseRelease`, the owner first closes admission for new requests and records its final accepted ledger sequence. Requests already accepted before that boundary may finish according to their commit state; requests arriving after it receive a retryable draining response. The release record must include the owner incarnation and epoch, so a late release from a predecessor cannot release its successor's lease. Clearing the owner field alone is not a valid release transition. The durable record must retain the fencing epoch and final sequence until the next acquisition incorporates them. If draining exceeds the deadline, switch to the expiration path and preserve the unresolved sequence range for recovery rather than declaring a clean handover.

A successful `LeaseRelease` response means that the manager has installed a no-new-writes fence for the releasing epoch and persisted the handover boundary. It does not mean every client has received its final acknowledgement. The releasing worker may replay previously committed outcomes, but it cannot allocate new request identifiers or attach new payloads. Repeating release with the same owner and boundary is idempotent. A repeat with a different final sequence must be rejected because it would redefine which requests recovery must examine. When a successor already owns the partition, the manager returns the recorded predecessor release outcome without modifying current ownership, extending deadlines or resetting the successor's renewal counter.

## Recovery

On `CrashRecover`, the lease manager treats the persisted owner record as a fencing obligation, not evidence that the old worker remains alive. Recovery compares the manager's current clock with the committed deadline and checks whether a successor epoch already exists. If a successor exists, the old epoch can only supply historical outcomes; no heartbeat, delayed commit or release can make it current again. If the deadline remains valid and no successor exists, recovery may resume the same incarnation only when its local durable incarnation record agrees. Losing that record requires a new acquisition. Guessing an incarnation from a process identifier or hostname would allow old in-flight requests to become indistinguishable from new work.

The `CrashRecover` result must report whether ownership resumed, expired or was superseded, together with the exact epoch used for subsequent reconciliation. A partial fence installation is resumed against both the ledger and payload subsystem before any write-capable result is returned. If those subsystems disagree about the highest epoch, select neither by majority nor by availability; expose the mismatch and hold write admission closed. Reads of already committed checkpoints may continue when their ownership history is intact. Recovery must persist its chosen transition before notifying the scheduler, because otherwise a second crash could produce a different owner decision and cause the same prepared request to be reconciled under two epochs.
""",
        "docs/ledger.md": """# Request ledger

## Acquisition

At `LeaseAcquire`, the request ledger opens an admission range tied to the partition and the newly installed fencing epoch. It reads the previous range's final sequence before allocating any sequence in the new range. Sequence numbers are monotonically increasing within the partition and are not restarted when a worker or machine changes. An acquisition identifier may reopen the same provisional range after an interrupted acknowledgement, but cannot create a second range for the same epoch. If a predecessor has unresolved entries, record their interval separately from the new admission cursor. They do not block all new reads, but no new write may reuse their request keys or interpret an unresolved predecessor response as its own result.

The ledger's `LeaseAcquire` acknowledgement is sent only after the range header and epoch fence have committed together. A header containing an owner name without the corresponding fence is not an available range. The acknowledgement includes the admitted epoch, first sequence and previous reconciliation boundary, allowing the coordinator to compare it with the lease manager's proposal. If the coordinator retries after a lost response, return those same values. Do not recalculate the first sequence from the number of visible payloads, since payloads can be prepared without a ledger commit. A storage error before transaction completion leaves the acquisition unacknowledged; an uncertain commit outcome requires reading the exact header before another allocation attempt.

## Renewal

During `LeaseRenew`, the ledger checks that its installed epoch still matches the renewing owner before accepting another batch of requests. Renewal does not allocate request sequences and cannot advance the admission cursor by itself. The coordinator may attach a new deadline observation to the range header for diagnostics, but the fencing epoch remains the write-admission authority. If the ledger discovers a newer epoch, it rejects both the renewal acknowledgement and queued requests from the older owner. Requests already committed under the old epoch retain their immutable outcome. This distinction prevents lease management traffic from rewriting business results while still ensuring that a worker with a stale local deadline cannot continue appending new operations.

The `LeaseRenew` path must not compact unresolved request entries simply because their client's retry interval has elapsed. An unresolved entry can refer to a payload whose commit response was lost, and its key remains reserved until reconciliation classifies it. Completed entries may move into an outcome archive only if the archive preserves the request digest, result digest and terminal sequence. A later retry must still distinguish identical input from a conflicting reuse of the key. Archive publication and removal from the active ledger form one logical transition; a crash between them must expose either a readable active outcome or a readable archived outcome, never a gap that allows the same request to execute again.

## Checkpoint

For `CheckpointCommit`, the ledger binds the checkpoint sequence to the exact ordered set of accepted request identifiers. A set with a missing middle sequence cannot be described as a contiguous checkpoint merely because its highest sequence exists. Each member supplies its input digest, prepared payload descriptor and terminal classification. The ledger verifies those values against the accepted entries before recording the checkpoint transaction. Conflicting retries are excluded and retain their conflict outcomes outside the checkpoint's successful member set. The coordinator cannot substitute a request with the same client label but different input bytes. If any descriptor is missing, retain the checkpoint as pending and identify the missing request rather than publishing a reduced checkpoint silently.

The ledger's `CheckpointCommit` transaction records a stable commit identifier that the payload pointer and acknowledgement outbox must both reference. Repeating the same commit identifier with the same membership returns its recorded result. Reusing it with a different order, payload digest or final sequence fails as a conflict even if the new proposal would contain more completed work. Once committed, the membership list is immutable and becomes the reconciliation witness for uncertain client responses. Failure to deliver those responses does not roll the transaction back. A checkpoint can be superseded by a later checkpoint, but its request outcomes remain addressable until the documented retry-retention boundary has advanced past every included sequence.

## Release

During `LeaseRelease`, the ledger freezes the releasing epoch's admission cursor and reports the last accepted sequence, not merely the last completed one. The distinction matters when a request has reserved a key but is waiting for payload preparation. The coordinator must receive a complete list of unresolved intervals between its last checkpoint and the frozen cursor. An empty interval list is valid only after checking every accepted entry in that range. The ledger cannot infer completion from a missing active row unless a committed archive entry accounts for it. If the release request names a different owner epoch, return a stale-owner result without freezing the current owner's cursor or altering the current admission range.

A retried `LeaseRelease` operation must preserve the same frozen sequence and unresolved interval digest. Later reconciliation may resolve entries inside those intervals, but it cannot change which entries were accepted before the release boundary. The ledger stores the release outcome separately from mutable reconciliation progress so both facts remain inspectable. A successor can allocate sequences after the frozen cursor while reconciling older work, provided it respects request-key reservations and payload references. The releasing worker may read its frozen range but may not append a late request to make its local queue appear drained. Such a request must be retried through the successor and receives a new sequence only after ordinary duplicate-key checks.

## Recovery

For `CrashRecover`, scan the ledger's durable acceptance range and classify every nonterminal entry before reclaiming its request key. A prepared payload does not by itself establish a committed request, and a recorded client timeout does not establish failure. Recovery checks the checkpoint commit identifier, payload pointer and outbox linkage associated with the entry. If the checkpoint transaction committed, reconstruct the original terminal result without executing the request again. If preparation exists without publication, retain a pending or aborted classification according to the recorded checkpoint outcome. When the available records disagree, preserve the reservation and report an unresolved inconsistency. Choosing the most convenient record would risk duplicate execution or loss of a committed result.

The `CrashRecover` cursor advances only after each examined entry's classification has been committed. Persisting a cursor beyond an unclassified entry is forbidden even when a later batch completed successfully. The cursor includes the generation of the acceptance range so a resumed scan cannot accidentally continue against a newly compacted view. Recovery batches are idempotent: replaying a batch after a lost response must preserve existing classifications and report their prior outcomes. An archive transition encountered during scanning must resolve through its committed forwarding record. If the archive cannot be read, stop at that sequence and retain the unresolved interval; do not treat temporary archive unavailability as evidence that the original request never existed.
""",
        "docs/payloads.md": """# Payload persistence

## Acquisition

On `LeaseAcquire`, the payload store installs the proposed fencing epoch before accepting mutable descriptors from the new owner. Existing immutable objects remain readable regardless of their creator's epoch, but attaching them to a new checkpoint requires the current owner. The store returns its highest installed epoch and rejects proposals below it. An equal-epoch retry is allowed only for the same partition and acquisition identifier. The coordinator must compare this acknowledgement with the ledger's range acknowledgement before enabling write admission. If the store has already installed a newer fence than the lease manager expected, it must expose that disagreement instead of accepting an older proposal because its staging directory happens to be empty.

The payload `LeaseAcquire` transition creates a staging namespace whose identity contains the partition and epoch, with separate identifiers for individual requests. The namespace is not a publication capability: readers continue to resolve objects through committed checkpoint pointers. Staging objects from a predecessor must not be renamed into the new namespace merely to avoid rewriting them. They can be reused only through an explicit immutable-content reference whose digest is verified and whose ownership history remains attached to the descriptor. An interrupted namespace creation is resumed idempotently from the acquisition record. The store must distinguish an existing matching namespace from an unrelated directory or object that happens to share its display name.

## Renewal

During `LeaseRenew`, the payload store can extend the retention deadline of staging objects owned by the current epoch, but must not change their content digests or publication state. The renewal acknowledgement names the staging namespace and the epoch whose fence was checked. A worker cannot renew objects belonging to a predecessor simply by presenting their paths. If a preparation upload is still in progress, renewal preserves its temporary status and expected digest; it does not certify that the full content arrived. Readers never discover these temporary objects through a listing operation. If the store cannot persist the retention extension, it returns an error and keeps the previously committed deadline rather than advertising a longer period that recovery cannot observe.

The `LeaseRenew` retention policy must account for requests awaiting a checkpoint outcome. Such objects remain protected from reclamation until the ledger classifies their preparation, even if their lease has expired. Ordinary age-based cleanup applies only after the store has a durable terminal classification and no committed checkpoint references the object. A renewed lease does not invalidate an existing reclamation decision for a different epoch. Conversely, a cleanup worker must recheck the reference set before deleting an eligible object because publication may have committed after the cleanup scan began. If reference verification is unavailable, leave the object in place and record deferred cleanup. Storage pressure is not permission to guess that an unacknowledged request was abandoned.

## Checkpoint

Before `CheckpointCommit`, the payload store finishes each object's write and verifies the complete byte digest against its accepted descriptor. A digest of only the most recently uploaded segment is insufficient. Object length, encoding-independent bytes and chunk ordering belong to the same descriptor. Once verified, the object becomes immutable; later retries can reuse it only if they present the same digest and length. A retry with different bytes must allocate a different object and cannot mutate the already prepared object in place. The checkpoint pointer remains unchanged until every required object is verified. If one object fails verification, report that descriptor specifically and preserve the previous readable checkpoint while the coordinator decides whether to retry or abort preparation.

At `CheckpointCommit`, publish the checkpoint pointer atomically with the commit identifier received from the ledger. The pointer contains the ordered immutable object descriptors and the fencing epoch used for publication. A reader must observe either the complete previous pointer or the complete new pointer, never a mixture assembled from separate directory listings. The store checks the current fence within the publication transaction. After success, loss of the response does not make the objects uncommitted: a repeated commit reads and returns the same pointer. A different proposal under the same commit identifier is rejected. The store retains the previous pointer long enough for in-flight readers to finish through their pinned checkpoint identity, rather than switching their object set midway through a read.

## Release

For `LeaseRelease`, stop accepting new preparations under the releasing epoch once its final ledger boundary is frozen. Already prepared objects retain their descriptors and remain available to reconciliation. The store returns a manifest of prepared but unpublished objects, bound to the epoch and final accepted sequence. A manifest cannot be declared empty based solely on an empty upload queue; completed uploads may still await pointer publication. The releasing worker must not delete those objects during local shutdown. The manifest's identity is persisted so a successor can compare repeated release acknowledgements and detect missing objects. If manifest construction fails, release remains incomplete at the payload boundary and recovery must examine the affected staging namespace explicitly.

The payload `LeaseRelease` acknowledgement separates publication closure from reclamation eligibility. Closing the namespace prevents new writes but does not authorize deletion of every unreferenced-looking file. The store retains objects until the ledger's frozen range has a terminal classification for their request identifiers. Published objects remain readable through any retained checkpoint reference. Unpublished terminally aborted objects can enter the ordinary reclamation queue, carrying their descriptor digests so the cleanup operation cannot remove a different object that later reused a storage slot. A repeated release returns the same closure manifest; subsequent cleanup progress is reported separately. This prevents a retry from hiding objects that were present when ownership was handed over.

## Recovery

During `CrashRecover`, verify each prepared object's stored length and complete digest before using it to reconstruct a checkpoint outcome. The presence of a final-looking filename is not evidence that an interrupted upload completed. Incomplete objects remain unavailable and are linked to their unresolved ledger entries. A committed checkpoint whose referenced object fails verification is a consistency failure, not an instruction to roll the checkpoint back to an older value. Recovery preserves the pointer and reports the damaged reference so the operator or repair process can restore the required bytes. It must not substitute another object merely because its title, request label or approximate size matches. Content identity remains exact throughout recovery.

The payload `CrashRecover` scan joins staging objects to ledger classifications and retained checkpoint references before scheduling cleanup. Objects referenced by a committed pointer survive even when their original lease owner has disappeared. Orphans without a ledger acceptance record are quarantined until the acquisition range and any interrupted namespace transaction have been examined. A scan records the generation of the pointer set it used; if publication advances during the scan, revalidate affected references before deleting anything. Recovery may report incomplete cleanup while still serving verified committed reads. It cannot claim the staging namespace is reconciled until every object has either an exact retained reference or a durable terminal classification authorizing its ordinary removal.
""",
        "docs/acknowledgements.md": """# Acknowledgement delivery

## Acquisition

During `LeaseAcquire`, the acknowledgement service binds a delivery session to the partition's new epoch without taking ownership of predecessor outcomes. The session may deliver only outcomes already linked to committed ledger records; acquiring a lease is not itself a successful business operation. The service records the client's stable request key separately from the worker incarnation so reconnecting through a successor still finds the original outcome. If a client reconnects while fencing is incomplete, the service may report pending status but must not synthesize success from an acquisition acknowledgement. The delivery session becomes write-capable only after the coordinator confirms both ledger and payload fences, and that confirmation must name the exact epoch selected for the session.

The `LeaseAcquire` delivery setup must preserve deduplication state across worker changes. A new session starts with the last durable delivery cursor and the unresolved outbox identifiers, rather than assuming that all messages before the reconnect were received. Client acknowledgement numbers are checked against the session's committed message identities. A client cannot acknowledge a message that was never published merely by supplying a large sequence number. If the service cannot read the previous delivery cursor, it may replay known committed outcomes with their original identifiers but cannot compact the outbox. Establishing a fresh network connection changes transport state only; it does not reset request identity, outcome retention or the ledger's accepted sequence range.

## Renewal

For `LeaseRenew`, the acknowledgement service refreshes the transport session's liveness independently from the business lease deadline. A successful heartbeat proves only that the client connection responded. It does not extend the worker's write authority or establish that pending requests committed. Delivery of already committed outcomes can continue after the worker's lease expires, provided each message retains its original commit identifier. The service must label pending notifications as pending and keep them distinct from terminal success messages. A heartbeat timeout may close the connection, but it must not turn every unresolved request into a terminal failure. Those requests remain discoverable through the durable outbox and ledger when the client reconnects.

The `LeaseRenew` retry path must not generate a new acknowledgement identifier for a previously queued terminal outcome. Identical replays use the same message identity and content digest, allowing the client to deduplicate without guessing whether a result changed. A renewal may update delivery-attempt metadata such as the last transport error, but cannot replace the outcome payload or its commit reference. Client acknowledgements received during renewal advance the durable delivery cursor only after validating contiguous receipt or explicitly recorded gaps. If persisting that cursor fails, retain the messages for replay. Sending duplicate committed outcomes is preferable to deleting an outcome based on an acknowledgement that existed only in volatile connection state.

## Checkpoint

At `CheckpointCommit`, create terminal-success outbox entries only after the ledger transaction and payload pointer agree on the same commit identifier. The outbox entry contains the request key, immutable result digest, checkpoint sequence and source epoch. A provisional payload descriptor must never be rendered as a completed result. If publication succeeds but outbox creation fails, the request remains committed and recovery must rebuild delivery from the ledger; the service must not ask the worker to execute the request again. Conversely, an outbox record without a matching committed checkpoint cannot be delivered as success. The coordinator reports that mismatch as pending reconciliation rather than choosing whichever subsystem answered first.

The acknowledgement side of `CheckpointCommit` must preserve the distinction between accepting a message for delivery and the client actually receiving it. The commit response can report that a durable outcome exists, but a network write alone does not advance the client receipt cursor. Terminal messages are serialized from the immutable ledger outcome, and the serialized content digest is retained for replay checks. If the same request key appears with a different digest under an existing commit identifier, stop delivery and expose the conflict. Do not overwrite the previous outbox entry to match the latest in-memory response. A retry after an uncertain socket result reads the durable outbox entry and repeats its exact identity and business content.

## Release

During `LeaseRelease`, the acknowledgement service stops creating messages from the releasing worker's volatile callbacks and switches to durable ledger outcomes. This prevents a delayed callback from announcing success for a request that never crossed the checkpoint boundary. Existing committed messages remain deliverable and retain their original identifiers. The release acknowledgement includes the last durable outbox sequence and any unresolved delivery gaps, which are separate from the ledger's last accepted request sequence. The coordinator must not compare those two counters as if they represented the same event stream. A drained network buffer is also insufficient evidence that all clients received their outcomes; the durable receipt cursor determines which messages still need replay.

A `LeaseRelease` retry must return the same durable handover cursor even if some clients have acknowledged messages since the first release attempt. New receipt progress is reported as a separate current cursor, preserving the original handover witness. The successor inherits outstanding delivery obligations without changing their source epochs or business digests. Messages for terminally rejected requests may still be delivered, but they must remain rejection outcomes and cannot be merged into a checkpoint success summary. If the releasing process exits before receiving the handover response, recovery uses the stored release record. It must not infer successful delivery from the absence of the old process or from the fact that its transport connection has closed.

## Recovery

On `CrashRecover`, rebuild missing outbox entries only from committed ledger outcomes whose payload pointers have been verified. The reconstruction uses the original request key and deterministic outcome identity, so a second recovery pass cannot create another business result. If a committed outcome already has an outbox entry, compare its immutable fields and retain its receipt state. A mismatch requires investigation and blocks that message; it must not be repaired by taking whichever content was written most recently. Requests with uncertain checkpoint status remain pending notifications, not successes or failures. Recovery can resume delivery of unrelated verified outcomes while clearly reporting the unresolved identifiers that prevented complete outbox reconstruction.

The delivery `CrashRecover` cursor tracks examined ledger outcomes separately from acknowledged client messages. Advancing reconstruction does not imply receipt. After restart, replay every committed message above the durable receipt boundary, including gaps explicitly retained below the highest acknowledged sequence. Transport errors may increase attempt counts but never change the business outcome or erase the message's commit reference. A client presenting a receipt from a different partition or session lineage must not advance this partition's cursor. When all reconstructable outcomes have been examined, report reconstruction complete even if clients remain offline; report delivery complete only when their durable receipt obligations are actually satisfied. These two completion states must remain distinguishable to the coordinator.
""",
        "docs/reconciliation.md": """# Recovery reconciliation

## Acquisition

Before completing `LeaseAcquire`, the reconciliation coordinator records the predecessor's unresolved intervals and the proposed successor epoch in a durable handover plan. The plan identifies which ledger range, payload namespace and acknowledgement cursor will be compared. It must not expand its scope by scanning unrelated partitions when one component is unavailable. A missing predecessor release record is represented as an incomplete handover, requiring an expiration-based inventory, rather than being treated as an empty workload. The successor may begin only the operations explicitly allowed while that inventory is pending. In particular, it cannot recycle unresolved request keys or remove predecessor staging objects merely because the lease manager has issued a newer epoch.

The reconciliation portion of `LeaseAcquire` must distinguish provisional ownership from a completed handover. It waits for the exact ledger and payload fence acknowledgements named in the plan and compares their epochs before marking the handover writable. An acknowledgement from an earlier acquisition attempt cannot satisfy a new plan even if the worker name matches. Repeating the same plan identifier reuses its recorded component outcomes. If one component reports a newer epoch, suspend the plan and expose the superseding identity instead of retrying with weakened comparisons. The handover record remains readable after failure so a subsequent coordinator can explain which component accepted the transition and which component still requires resolution.

## Renewal

During `LeaseRenew`, reconciliation may continue processing predecessor intervals, but the renewal itself does not classify any request. Each classification still requires the appropriate ledger, payload and outbox witnesses. The coordinator records which owner epoch is authorized to publish reconciliation progress and rejects updates from a superseded worker. A long-running scan must periodically check that fence before committing another batch. It can retain read-only findings after losing ownership, but those findings must be revalidated by the successor before they produce writes. Renewal failures are reported separately from classification failures; otherwise a transient lease-management error could incorrectly turn an uncertain business operation into a terminal aborted request.

The `LeaseRenew` scheduling policy must preserve progress without starving newly accepted work. Reconciliation batches use a bounded sequence interval and persist their next cursor only after classifications commit. Extending the lease may permit another batch, but it cannot silently enlarge a batch already in progress to include newly discovered partitions or unrelated namespaces. When a required component is temporarily unavailable, record the exact blocked interval and yield rather than spinning on an unbounded retry loop. A later renewal can reschedule that same interval using its existing identity. The coordinator must keep operational retry decisions separate from business classification so retry exhaustion means reconciliation is incomplete, not that every blocked request failed.

## Checkpoint

For `CheckpointCommit`, reconciliation verifies that the proposed checkpoint does not cross an unresolved predecessor interval that affects its request-key namespace. A sequence number greater than the predecessor's final sequence is not enough if the new checkpoint reuses an unresolved key. The coordinator compares accepted input digests and terminal outcomes before allowing that reuse. Independent request keys can proceed when their ownership and payload references are sound, but the checkpoint must record any deliberately excluded pending interval. Exclusion is explicit data, not a claim that the omitted requests were rejected. If publication needs a contiguous range, unresolved members block that checkpoint until they are classified; the coordinator cannot redefine contiguity after seeing which results arrived.

After `CheckpointCommit`, reconciliation records the commit identifier as an immutable observation and verifies that the ledger membership, payload pointer and outbox outcomes agree. A missing outbox entry is a delivery repair task, while a missing payload reference is a consistency failure; these cases require different actions. Neither permits replaying the business operation under a new request identity. The coordinator persists the classification and any repair obligation before advancing its reconciliation cursor. If a crash occurs between observing the commit and recording that classification, the next pass must rediscover the same commit and produce the same result. A later checkpoint can add progress but cannot retroactively alter the original checkpoint's member set or ownership epoch.

## Release

At `LeaseRelease`, reconciliation collects the ledger's frozen acceptance boundary, the payload closure manifest and the acknowledgement handover cursor into one release report. The report retains each component's own sequence domain instead of collapsing them into a single highest number. It identifies unresolved business requests separately from undelivered committed outcomes and deferred object cleanup. A release can be operationally complete while delivery remains pending, but it cannot be described as fully reconciled while business classifications are unknown. If a component response is missing, preserve the partial report with that component explicitly absent. Filling the gap with an empty list would erase the successor's obligation to inspect it after handover.

The reconciliation `LeaseRelease` report is bound to the releasing epoch and the exact component manifest identities. Repeating release compares those identities with the stored report and returns the same handover boundary. Subsequent cleanup and delivery receipts update separate progress records. A predecessor cannot revise its report after a successor starts accepting work, because doing so would change the ownership boundary used to classify late requests. If a delayed component acknowledgement disagrees with the stored report, record an inconsistency and stop the affected reconciliation transition. The coordinator must not choose a newer-looking manifest without checking whether it belongs to another epoch or to work accepted after the original release boundary.

## Recovery

On `CrashRecover`, reopen the latest durable handover or release plan and resume from its committed reconciliation cursor. Validate the plan's partition, epochs, ledger generation and component manifest identities before using any cached finding. The coordinator must distinguish an operation that was never accepted, an accepted but unpublished preparation, a committed result awaiting delivery and an inconsistent committed reference. Each classification has a different retry or repair consequence. An unavailable component leaves the classification unresolved; it is not evidence for the least expensive outcome. Recovery reports the exact unresolved interval and component so the caller can continue unrelated verified work without mistaking partial availability for complete consistency.

The final `CrashRecover` completion record requires a classification for every accepted sequence in scope and an explicit disposition for every inventoried staging object and outbox obligation. Business reconciliation, object cleanup and client delivery have separate completion flags with separate evidence. The coordinator may complete business reconciliation while cleanup is deferred or clients are offline, but it must preserve those remaining obligations durably. A second recovery pass reads that completion record and verifies its referenced generations before declaring no work necessary. If the underlying ledger or pointer generation changed, it resumes the affected checks instead of trusting an old completion boolean. The record summarizes verified observations; it never grants permission to skip source, epoch or request-identity comparisons.
""",
    }


def payload(result: object, *, allow_error: bool = False) -> dict:
    assert allow_error or not getattr(result, "isError", False), result
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    content = getattr(result, "content", [])
    assert len(content) == 1 and isinstance(getattr(content[0], "text", None), str), result
    value = json.loads(content[0].text)
    assert isinstance(value, dict), value
    return value


def text_payload(result: object, *, allow_error: bool = False) -> dict:
    if getattr(result, "structuredContent", None) is not None:
        raise AssertionError("text-only compatibility response included structuredContent")
    return payload(result, allow_error=allow_error)


def validate_context_payload(answer: dict, *, required_fragment: str) -> None:
    assert answer.get("status") == "ok", answer
    assert answer.get("kind") in {"docs_answer", "docs_context"}, answer
    if answer["kind"] == "docs_context":
        assert answer.get("support_status") == "retrieval_only", answer
        assert answer.get("context_status") == "ready", answer
        assert answer.get("answer_supported") is False, answer
        assert answer.get("answer_available") is False, answer
    else:
        assert answer.get("support_status") == "supported", answer
        assert answer.get("answer_supported") is True, answer
        assert answer.get("answer_available") is True, answer
    assert required_fragment in json.dumps(answer), answer
    assert answer.get("sources"), answer
    for source in answer["sources"]:
        assert source.get("path_or_url") and source.get("snippet"), source
        digest = source.get("content_sha256", "")
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), source


def validate_patch_payload(answer: dict, *, completeness: str | None = None) -> None:
    from docmancer.docs.application.action_packet import (
        estimate_action_packet_tokens, refresh_action_packet_estimate, validate_action_packet,
    )

    assert answer.get("kind") == "patch_context" and answer.get("schema_version") == 4, answer
    assert answer.get("estimated_tokens") == estimate_action_packet_tokens(answer), answer
    # Only the documented projection envelope is removed. Unknown fields remain
    # visible to the strict validator. Keep returned sources/assignments intact.
    packet = {key: value for key, value in answer.items()
              if key not in {"kind", "recommended_next_action", "source_search_status"}}
    assert packet.get("sources") is answer.get("sources")
    assert packet.get("assignments") is answer.get("assignments")
    refresh_action_packet_estimate(packet)
    errors = validate_action_packet(packet)
    assert not errors, errors
    if completeness is not None:
        assert answer.get("completeness") == completeness, answer


def _accept_fixture(project: Path) -> None:
    for args in (("init", "-q"), ("config", "core.autocrlf", "false"),
                 ("config", "user.email", "fixture@example.test"),
                 ("config", "user.name", "Docs MCP smoke fixture"),
                 ("add", "."), ("commit", "-qm", "accepted fixture documentation")):
        subprocess.run(["git", "-C", str(project), *args], stdin=subprocess.DEVNULL,
                       check=True, timeout=15)


def _read_fixture_job_state(database: Path, job_id: str) -> tuple[str] | None:
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
        return db.execute("SELECT status FROM docs_jobs WHERE job_id = ?", (job_id,)).fetchone()


def isolated_environment(root: Path) -> dict[str, str]:
    # Do not inherit caller config, credentials, Python overlays or provider flags.
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
           if key in os.environ}
    for key, relative in {"HOME": "user-home", "USERPROFILE": "user-home",
                          "XDG_CONFIG_HOME": "config", "XDG_DATA_HOME": "data",
                          "XDG_CACHE_HOME": "cache", "DOCATLAS_HOME": "docatlas-home"}.items():
        path = root / relative
        path.mkdir(exist_ok=True, mode=0o700)
        env[key] = str(path)
    env.update({"PYTHONNOUSERSITE": "1", "DOCATLAS_AUTO_VECTORS": "0",
                "DOCATLAS_REGISTRY_API_URL": "http://127.0.0.1:1", "NO_PROXY": "*"})
    return env


async def read_only_delivery(session, project: Path, *, text_only: bool) -> None:
    decode = text_payload if text_only else payload
    names = {tool.name for tool in (await session.list_tools()).tools}
    assert names == TOOLS, names
    canonical_query = {"question": QUESTION, "project_path": str(project)}
    assert set(canonical_query) == {"question", "project_path"}
    result = await session.call_tool("get_docs_context", canonical_query)
    if not text_only:
        assert isinstance(result.structuredContent, dict), result
    docs = decode(result, allow_error=True)
    assert docs.get("kind") != "patch_context", docs
    assert not docs.get("edit_ready") and not docs.get("answer_supported"), docs
    assert docs.get("status") == "failed" and not docs.get("sources"), docs
    assert docs["error"]["reason_code"] == "permission_denied", docs
    patch = decode(await session.call_tool("get_docs_context", {
        **canonical_query, "context_format": "patch_context"}), allow_error=True)
    assert patch.get("status") == "failed" and not patch.get("sources"), patch
    assert patch["error"]["reason_code"] == "permission_denied", patch
    negative_bindings = {}
    for name, extra in (("module_mismatch", {"scope": "module", "module_path": "missing-module"}),
                        ("version_mismatch", {"version": "99.0.0"})):
        response = decode(await session.call_tool("get_docs_context", {
            **canonical_query, **extra, "context_format": "patch_context"}), allow_error=True)
        assert response.get("status") == "failed" and not response.get("sources"), response
        negative_bindings[name] = {"status": response["status"],
                                   "sources": [], "source_bytes": 0}
    for extra in ({"mutation_intent": {"operation": "delete", "confirm": True}},
                  {"edit_ready": True}, {"allow_network": True, "consent": True}):
        rejected = await session.call_tool("get_docs_context", {**canonical_query, **extra})
        if not rejected.isError:
            response = decode(rejected)
            assert response.get("status") in {"error", "failed"}, response
    assert (project / "README.md").read_text().endswith(f"`{NEEDLE}`.\n")
    print(f"Installed {'text' if text_only else 'structured'} unindexed read-only observations: " + json.dumps({
        "docs_default": {"status": docs.get("status"), "kind": docs.get("kind"),
                         "sources": docs.get("sources", []),
                         "source_bytes": sum(len(row.get("snippet", "").encode()) for row in docs.get("sources", []))},
        "cold_patch": {"status": patch["status"], "reason": patch["error"]["reason_code"],
                        "sources": [], "source_bytes": 0},
        "negative_bindings": negative_bindings, "unauthorized_fields": "rejected; target unchanged"}, sort_keys=True))


async def indexed_delivery(session, project: Path, database: Path, *, text_only: bool) -> tuple[dict, str]:
    decode = text_payload if text_only else payload
    mutation = cold_fixture_members(project, database)
    assert not database.exists() and not database.parent.exists()
    rejected = await session.call_tool("prepare_docs", {
        "action": "sync_project_docs", "project_path": str(project)})
    assert decode(rejected, allow_error=True).get("status") != "success"
    assert not database.parent.exists(), "missing grant provisioned member namespace"
    prepared = decode(await session.call_tool("prepare_docs", {
        "action": "sync_project_docs", "project_path": str(project), "mutation": mutation}))
    assert prepared.get("status") == "success", prepared
    generation = prepared["metrics"]["generation_id"]
    assert generation.startswith("gen-")
    assert database.stat().st_mode & 0o777 == 0o600
    assert database.parent.stat().st_mode & 0o777 == 0o700
    assert not (project / ".docatlas" / "docatlas.db").exists()
    answer = decode(await session.call_tool("get_docs_context", {"question": QUESTION, "project_path": str(project)}))
    validate_context_payload(answer, required_fragment=NEEDLE)
    print("Cold confirmed preparation/retrieval: " + json.dumps({"transport": "text" if text_only else "structured",
          "database": str(database), "generation_id": generation, "fixture_bootstrap": False,
          **evidence_sizes(answer, project)}, sort_keys=True))
    return mutation, generation


async def repeat_preparation(session, project: Path, database: Path, mutation: dict, generation: str, *, text_only: bool):
    decode = text_payload if text_only else payload
    before = fixture_database_state(database)
    request = {"action": "sync_project_docs", "project_path": str(project),
               "mutation": {**mutation, "expected_generation_id": generation}}
    repeated = decode(await session.call_tool("prepare_docs", request))
    assert repeated.get("status") == "success", repeated
    assert repeated["metrics"]["generation_id"] == generation and repeated["metrics"]["derived_writes"] == 0, repeated
    stale = decode(await session.call_tool("prepare_docs", {**request, "mutation": mutation}), allow_error=True)
    assert stale.get("status") != "success", stale
    answer = decode(await session.call_tool("get_docs_context", {"question": QUESTION, "project_path": str(project)}))
    validate_context_payload(answer, required_fragment=NEEDLE)
    assert fixture_database_state(database) == before
    print("Restart/repeat/CAS: " + json.dumps({"transport": "text" if text_only else "structured",
          "generation_id": generation, "derived_writes": 0, "stale_null_rejected": True,
          "source_generation_rows_unchanged": True}, sort_keys=True))


def cold_fixture_members(project: Path, database: Path) -> dict:
    """Author source grants without constructing or opening the selected store."""
    from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
    from docmancer.docs.project_docs_catalog import read_project_docs_catalog

    for path, text in natural_protocol_documents().items():
        target = project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    documents = [{"path": path, "role": "overview", "scope": "project", "description": "Fixture",
                  "authority": "source_of_truth"} for path in ("README.md", *natural_protocol_documents())]
    for name in ("alpha", "beta"):
        module = project / "packages" / name
        module.mkdir(parents=True)
        (module / "pyproject.toml").write_text(f'[project]\nname = "fixture-{name}"\nversion = "1.0.0"\n')
        (module / "README.md").write_text(f"# {name.title()} transport\n\nThe {name} transport command is `{name}-start`.\n")
        documents.append({"path": f"packages/{name}/README.md", "role": "module_architecture", "scope": "module",
                          "module_path": f"packages/{name}", "description": name, "authority": "source_of_truth"})
    catalog = project / "docatlas.project-docs.yaml"
    catalog.write_text(json.dumps({"schema_version": 1, "code_files": [], "documents": documents}, sort_keys=True))
    _accept_fixture(project)
    entries = read_project_docs_catalog(project).entries
    return {"operation": "sync_project_docs", "confirm": True, "storage_path": str(database),
            "expected_generation_id": None, "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
            "documents": [{"path": row.path, "content_sha256": hashlib.sha256((project / row.path).read_bytes()).hexdigest(),
                           "catalog_entry_hash": catalog_entry_hash(row)} for row in entries]}


def validate_blocked_preparation(response: dict) -> None:
    assert response.get("status") == "blocked", response
    assert response.get("reason_code") == "unsafe_sqlite_path_mutation", response
    assert response.get("retryable") is False and response.get("mutation_performed") is False, response


def initialize_fixture_members(project: Path):
    """Explicit fixture-author initialization, not an MCP mutation side effect."""
    from docmancer.core.sqlite_store import SQLiteStore
    from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
    from docmancer.docs.project_docs_catalog import read_project_docs_catalog

    for path, text in natural_protocol_documents().items():
        destination = project / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
    (project / "docatlas.yaml").write_text("index:\n  db_path: .docatlas/docatlas.db\n", encoding="utf-8")
    catalog = {"schema_version": 1, "code_files": [], "documents": [
        {"path": path, "role": "overview", "scope": "project", "description": "Fixture"}
        for path in ("README.md", *natural_protocol_documents())]}
    catalog_path = project / "docatlas.project-docs.yaml"
    catalog_path.write_text(json.dumps(catalog, sort_keys=True), encoding="utf-8")
    _accept_fixture(project)
    store = SQLiteStore(project / ".docatlas" / "docatlas.db")
    with store._connect() as conn:
        assert store._active_generation_id(conn) is None
    entries = {entry.path: entry for entry in read_project_docs_catalog(project).entries}
    mutation = {"operation": "sync_project_docs", "confirm": True,
        "storage_path": str(store.db_path), "expected_generation_id": None,
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "documents": [{"path": path, "content_sha256": hashlib.sha256((project / path).read_bytes()).hexdigest(),
                       "catalog_entry_hash": catalog_entry_hash(entries[path])} for path in entries]}
    return store, mutation


def fixture_database_state(database: Path) -> dict:
    """Read-only member state; excludes lifecycle job rows deliberately."""
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as conn:
        return {table: conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
                for table in ("sources", "sections", "index_generations", "generation_sources", "retrieval_parents",
                              "retrieval_children", "retrieval_children_fts")}


def fixture_database_fingerprint(database: Path) -> dict[str, str]:
    return {suffix: hashlib.sha256(path.read_bytes()).hexdigest()
            for suffix in ("", "-wal", "-shm", "-journal")
            if (path := Path(str(database) + suffix)).exists()}


def bootstrap_ready_fixture(project: Path) -> dict:
    """Fixture author setup, never preparation acceptance or legacy migration."""
    from docmancer.core.models import Document
    from docmancer.core.sqlite_store import SQLiteStore
    from docmancer.docs.application.project_docs_member_transaction import local_project_identity
    from docmancer.docs.project import ProjectMetadataReader

    catalog_path = project / "docatlas.project-docs.yaml"
    catalog = json.loads(catalog_path.read_text())
    for entry in catalog["documents"]:
        entry["authority"] = "source_of_truth"
    for name in ("alpha", "beta"):
        module = project / "packages" / name
        module.mkdir(parents=True)
        (module / "pyproject.toml").write_text(f'[project]\nname = "fixture-{name}"\nversion = "1.0.0"\n')
        (module / "README.md").write_text(
            f"# {name.title()} transport\n\nThe {name} transport command is `{name}-start`.\n", encoding="utf-8")
        catalog["documents"].append({"path": f"packages/{name}/README.md", "role": "module_architecture",
            "scope": "module", "module_path": f"packages/{name}", "description": f"Fixture {name} transport",
            "authority": "source_of_truth"})
    catalog_path.write_text(json.dumps(catalog, sort_keys=True), encoding="utf-8")
    (project / ".gitignore").write_text(".docatlas/\n", encoding="utf-8")
    _accept_fixture(project)
    metadata = ProjectMetadataReader().read(project)
    assert metadata.docs_catalog_valid, metadata.warnings
    identity = local_project_identity(project)
    documents = []
    provenance = {}
    for candidate in metadata.docs_candidates:
        path = project / candidate.path
        content = path.read_bytes().decode("utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert candidate.content_hash == "sha256:" + digest
        document_metadata = {
            "project_path": str(project), "project_identity": identity, "repository_identity": identity,
            "source_class": "project_file", "project_docs": True, "source_path": candidate.path,
            "project_doc_path": candidate.path, "project_doc_content_hash": candidate.content_hash,
            "project_doc_catalog_entry_hash": candidate.catalog_entry_hash,
            "project_doc_mtime_ns": candidate.mtime_ns, "project_doc_reason": candidate.reason,
            "doc_scope": candidate.doc_scope, "module_path": candidate.module_path,
            "module_id": candidate.module_id, "module_name": candidate.module_name,
            "module_type": candidate.module_type, "project_doc_description": candidate.description,
            "project_doc_authority": candidate.authority, "project_doc_lifecycle_status": candidate.lifecycle_status,
            "lifecycle_status": candidate.lifecycle_status, "project_doc_impact_policy": candidate.impact_policy,
            "index_freshness": "synchronized",
        }
        documents.append(Document(source=str(path), content=content, metadata=document_metadata))
        provenance[candidate.path] = {"content_sha256": digest, "bytes": len(path.read_bytes()),
                                     "scope": candidate.doc_scope, "module_path": candidate.module_path}
    store = SQLiteStore(project / ".docatlas" / "docatlas.db")
    result = store.add_documents(documents)
    return {"generation_id": result.generation_id, "project_identity": identity,
            "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(), "files": provenance}


def evidence_sizes(response: dict, project: Path) -> dict:
    """Count returned bytes and union actual source spans; never wire wrappers."""
    sources = response.get("sources", [])
    total = 0
    intervals = {}
    details = []
    for row in sources:
        text = row.get("text", row.get("snippet", ""))
        path = row.get("path", row.get("path_or_url", ""))
        total += len(text.encode("utf-8"))
        detail = {"path": path, "evidence_id": row.get("evidence_id"),
                  "bytes": len(text.encode("utf-8")), "content_sha256": row.get("content_sha256")}
        start, end = row.get("char_start"), row.get("char_end")
        parsed = urlparse(path)
        source = (Path(url2pathname(parsed.path)) if parsed.scheme == "file" else project / path).resolve()
        assert source.is_relative_to(project.resolve()) and source.is_file(), row
        raw = source.read_bytes().decode("utf-8")
        if "text" in row:
            assert type(start) is int and type(end) is int and raw[start:end] == text, row
            assert hashlib.sha256(text.encode()).hexdigest() == row["content_sha256"], row
            detail["span_basis"] = "returned patch span"
        else:
            assert text and raw.count(text) == 1, "docs snippet cannot be uniquely bound for byte measurement"
            start = raw.index(text)
            end = start + len(text)
            detail["span_basis"] = "unique exact docs snippet occurrence; reporting only, not an added witness"
        intervals.setdefault(str(source), []).append((start, end))
        detail.update(char_start=start, char_end=end)
        details.append(detail)
    unique = 0
    for path, spans in intervals.items():
        merged = []
        for start, end in sorted(spans):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        raw = Path(path).read_bytes().decode("utf-8")
        unique += sum(len(raw[start:end].encode("utf-8")) for start, end in merged)
    return {"source_text_utf8_bytes": total, "unique_nonoverlap_utf8_bytes": unique,
            "unique_span_measurement": "returned patch spans / uniquely located exact docs snippets", "sources": details}


def trace_project_delivery(service, arguments: dict, project: Path) -> dict:
    """One real source-level public request; observers never alter results.

    Call separately from installed stdio acceptance. The caller supplies the
    same selected fixture storage/service; this helper never resolves storage,
    changes budgets, bootstraps evidence, or retries a failed request.
    """
    from unittest.mock import patch
    from docmancer.retrieval.dispatch import RetrievalDispatcher
    from docmancer.docs.application import _project_docs_service_part03 as project_service
    from docmancer.mcp.docs_server import call_docs_tool_payload

    acquired, qualified, routes = [], [], []
    dispatch = RetrievalDispatcher.run
    qualify = project_service._qualify_candidate_lookups

    def source_rows(chunks):
        rows = []
        for chunk in chunks:
            metadata = chunk.metadata or {}
            start, end = metadata.get("char_span") or (None, None)
            rows.append({"path": metadata.get("project_doc_path") or chunk.source,
                         "text": chunk.text, "char_start": start, "char_end": end,
                         "content_sha256": metadata.get("content_hash"),
                         "evidence_id": metadata.get("stable_chunk_id")})
        return rows

    def observe_dispatch(dispatcher, query, **kwargs):
        result = dispatch(dispatcher, query, **kwargs)
        rows = source_rows(result.chunks)
        acquired.extend(rows)
        routes.append({"query": query, "limit": kwargs.get("limit"), "budget": kwargs.get("budget"),
                       "expand": kwargs.get("expand"), "filters": dict(kwargs.get("filters") or {}),
                       **evidence_sizes({"sources": rows}, project)})
        return result

    def observe_qualification(*args, **kwargs):
        result = qualify(*args, **kwargs)
        qualified.extend(source_rows([chunk for chunk in result if any(
            match.get("qualified") is True
            for match in ((chunk.metadata or {}).get("retrieval_query_matches") or {}).values())]))
        return result

    with patch.object(RetrievalDispatcher, "run", observe_dispatch), patch.object(
            project_service, "_qualify_candidate_lookups", observe_qualification):
        response = call_docs_tool_payload("get_docs_context", arguments, service)
    validate_patch_payload(response)
    return {"measurement": "real in-process public route; NOT installed stdio or lifecycle acceptance",
            "routes": routes, "acquired": evidence_sizes({"sources": acquired}, project),
            "qualified": evidence_sizes({"sources": qualified}, project),
            "returned": evidence_sizes(response, project), "result": response.get("result"),
            "completeness": response.get("completeness"), "missing": response.get("missing", []),
            "payload_utf8_bytes": len(json.dumps(response, ensure_ascii=False).encode()),
            "tool_wire_utf8_bytes": None, "wire_note": "measure actual CallToolResult in stdio smoke"}


def bootstrap_library_fixture(project: Path, index_root: Path, *, database: Path | None = None) -> dict:
    """Real local authored versions, no remote URL, fetch, or external claim."""
    from docmancer.core.config import DocmancerConfig
    from docmancer.core.models import Document
    from docmancer.core.product_identity import ensure_owned_home
    from docmancer.core.sqlite_store import SQLiteStore
    from docmancer.docs.infrastructure.agent_index_gateway import AgentIndexGateway
    from docmancer.docs.registry import LibraryRegistry

    if database is None:
        database = project / ".docatlas" / "docatlas.db"
        ensure_owned_home(index_root.parent)  # Explicit fresh diagnostic fixture home.
    else:
        assert database.is_file(), "library preload must follow actual cold preparation"
    registry = LibraryRegistry(database)
    config = DocmancerConfig(index={"db_path": str(database)})
    gateway = AgentIndexGateway(config, library_index_root=index_root)
    now = datetime.now(timezone.utc).isoformat()
    fixtures = {}
    for version, command in (("1.0.0", "fixture-open"), ("2.0.0", "fixture-connect")):
        directory = project / "library-fixtures" / version
        directory.mkdir(parents=True)
        path = directory / "reference.md"
        content = f"# Local transport fixture {version}\n\nFor authored version {version}, the transport command is `{command}`.\n"
        path.write_text(content, encoding="utf-8")
        record = registry.upsert(library="local-transport-fixture", ecosystem=None, version=version,
            source_type="api", docs_url=directory.as_uri(), now=now, status="available",
            last_refreshed_at=now, requested_version=version, resolved_version=version,
            version_source="explicit", version_inferred=False,
            docs_snapshot_exact=True)  # Author selected the exact local version directory/bytes.
        indexed = gateway.index_config_for(record)
        metadata = {"library_id": record.library_id, "canonical_id": record.canonical_id,
                    "resolved_version": version, "version": version, "docs_snapshot_exact": True,
                    "source_class": "library_doc", "doc_scope": "library", "authority": "official",
                    "docset_root": directory.as_uri(), "canonical_url": path.as_uri(),
                    "source_origin_url": path.as_uri()}
        store = SQLiteStore(indexed.index.db_path, extracted_dir=indexed.index.extracted_dir)
        result = store.add_documents([Document(source=path.as_uri(), content=content, metadata=metadata)])
        fixtures[version] = {"source": path.as_uri(), "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "generation_id": result.generation_id, "database": str(store.db_path)}
    _accept_fixture(project)
    return fixtures


async def prepared_delivery_matrix(session, project: Path, database: Path, libraries: dict, *, text_only: bool,
                                   include_large: bool = True) -> list[str]:
    decode = text_payload if text_only else payload
    library_before = {version: fixture_database_state(Path(row["database"])) for version, row in libraries.items()}
    before = fixture_database_state(database)
    before_bytes = fixture_database_fingerprint(database)
    queries = {
        "docs_default": {"question": QUESTION},
        "docs_null": {"question": QUESTION, "context_format": None},
        "complete": {"question": "What command is documented as `doc-atlas mcp docs-serve`?"},
        "partial": {"question": "What command is documented as `doc-atlas mcp docs-serve` and `AbsentFixtureConstraint`?",
                    "lookup_queries": [NEEDLE]},
        "project_scope": {"question": QUESTION, "scope": "project"},
        "module_alpha": {"question": "What is the `alpha-start` transport command?", "module_path": "packages/alpha"},
        "module_beta": {"question": "What is the `beta-start` transport command?", "scope": "module", "module_path": "packages/beta"},
        "all_scope": {"question": "Which transport commands are `alpha-start` and `beta-start`?", "scope": "all",
                      "lookup_queries": ["alpha-start", "beta-start"]},
        "version_mismatch": {"question": QUESTION, "version": "99.0.0"},
        "module_mismatch": {"question": QUESTION, "module_path": "missing-module"},
        "large": {"question": LARGE_QUESTION, "lookup_queries": list(LARGE_PHASES)},
        "library_v1": {"question": "What is the `fixture-open` transport command?", "library": "local-transport-fixture", "version": "1.0.0"},
        "library_v2": {"question": "What is the `fixture-connect` transport command?", "library": "local-transport-fixture", "version": "2.0.0"},
        "library_missing_version": {"question": "What is the transport command?", "library": "local-transport-fixture", "version": "99.0.0"},
    }
    outcomes = {}
    blockers = []
    if not include_large:
        queries.pop("large")  # Exactly one large installed attempt across transports.
    for name, query in queries.items():
        arguments = query.copy() if name.startswith("library_") else {"project_path": str(project), **query}
        if name not in {"docs_default", "docs_null"}:
            arguments["context_format"] = "patch_context"
        wire = await session.call_tool("get_docs_context", arguments)
        outcome = {"tool_wire_utf8_bytes": len(wire.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")),
                   "tool_wire_measurement": "serialized CallToolResult, excluding JSON-RPC envelope/framing"}
        try:
            response = decode(wire, allow_error=True)
            outcome.update({key: response.get(key) for key in ("status", "result", "completeness", "missing")})
            assert not wire.isError, response
            # Count exact returned source bytes even if the wire contract fails;
            # the separate check/gate still fails and cannot certify delivery.
            outcome.update(evidence_sizes(response, project))
            if name in {"docs_default", "docs_null"}:
                validate_context_payload(response, required_fragment=NEEDLE)
            else:
                validate_patch_payload(response)
            if name in {"complete", "partial", "large"}:
                expected = "complete" if name == "large" else name
                assert response["result"] == "data" and response["completeness"] == expected, response
                if name == "large":
                    assert {row["path"] for row in response["sources"]} == set(natural_protocol_documents()), response
            if name in {"project_scope", "module_alpha", "module_beta", "all_scope"}:
                assert response["result"] == "data", response
                paths = {row["path"] for row in response["sources"]}
                if name == "project_scope":
                    assert paths <= {"README.md", *natural_protocol_documents()}, paths
                elif name in {"module_alpha", "module_beta"}:
                    module = "alpha" if name == "module_alpha" else "beta"
                    assert paths == {f"packages/{module}/README.md"}, paths
                else:
                    assert {"packages/alpha/README.md", "packages/beta/README.md"} <= paths, paths
            if name in {"library_v1", "library_v2"}:
                version = "1.0.0" if name == "library_v1" else "2.0.0"
                assert response["result"] == "data" and response["completeness"] == "complete", response
                assert {row["path"] for row in response["sources"]} == {libraries[version]["source"]}, response
                assert all(row.get("version_binding") == "exact_snapshot" for row in response["sources"]), response
                assert any(row["requirement_id"] == f"exact_version:{version}" for row in response.get("assignments", [])), response
            if name in {"version_mismatch", "module_mismatch", "library_missing_version"}:
                assert response["completeness"] != "complete", response
            outcome["check"] = "observed"
        except (AssertionError, KeyError, ValueError) as exc:
            outcome["check"] = "BLOCKED"
            outcome["error"] = str(exc)
            if wire.isError:
                outcome["transport_error"] = [getattr(part, "text", "") for part in wire.content]
            blockers.append(f"{name}: {exc}")
        if name == "large":
            passed = outcome.get("check") == "observed" and outcome.get("unique_nonoverlap_utf8_bytes", 0) > 32768
            outcome["gate"] = "PASS" if passed else "BLOCKED_upstream"
            if not passed:
                blockers.append(">32KiB unique source evidence not delivered under unchanged acquisition; see actual span measurements")
        outcomes[name] = outcome
    after = fixture_database_state(database)
    assert after == before, "public fixture reads changed indexed evidence generation/member state"
    assert {version: fixture_database_state(Path(row["database"])) for version, row in libraries.items()} == library_before, "library public reads changed evidence generation"
    print(f"Installed {'text' if text_only else 'structured'} PREPARED DELIVERY: " + json.dumps({
        "project_preparation": "confirmed cold MCP sync; no fixture database bootstrap",
        "library_preload": "authored local library indexes/registry only; NOT lifecycle acceptance",
        "local_library_provenance": libraries, "matrix": outcomes, "source_generation_rows_unchanged": True,
        "library_generation_rows_unchanged": True,
        "whole_database_bytes_unchanged": fixture_database_fingerprint(database) == before_bytes,
        "whole_database_note": "registry/job initialization can change other tables; distinct from indexed evidence",
        "library_lineage_note": "Original indexed child lineage retained; carrier is ordinary data, never authority; local authored provenance only"}, sort_keys=True))
    return blockers


async def invalid_manifest_lifecycle(session, project: Path, database: Path, decode) -> None:
    manifest = project.parent / f"{project.name}-invalid.docs.yaml"
    manifest.write_text("schema_version: 1\ntargets: not-a-list\n", encoding="utf-8")
    started = decode(await session.call_tool("prepare_docs", {
        "action": "prefetch_docs_manifest", "manifest_path": str(manifest), "project_path": str(project)}))
    assert started["status"] == "running" and started["job_id"], started
    # Fixture-only infrastructure barrier. One MCP status call follows terminal
    # failure; this is not model polling or permission inferred from status.
    deadline = time.monotonic() + 10
    while _read_fixture_job_state(database, started["job_id"]) != ("failed",):
        if time.monotonic() >= deadline:
            raise TimeoutError("local invalid manifest fixture did not reach failed state")
        await asyncio.sleep(0.01)
    terminal = decode(await session.call_tool("docs_status", {"action": "job", "job_id": started["job_id"],
                                                             "project_path": str(project)}), allow_error=True)
    assert terminal["status"] == "failed" and terminal["retryable"] is False, terminal
    assert terminal["counts"]["pages"]["total"] == 0, terminal


async def smoke(*, read_only: bool = False) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import docmancer

    checkout = Path(__file__).resolve().parents[1]
    imported = Path(docmancer.__file__).resolve()
    assert not imported.is_relative_to(checkout), f"smoke imported checkout instead of installed wheel: {imported}"
    assert imported.is_relative_to(Path(sys.prefix).resolve()), f"smoke must use its isolated wheel environment: {imported}"
    assert not os.environ.get("PYTHONPATH"), "installed smoke must not use a source PYTHONPATH"
    print("Installed artifact: " + json.dumps({"module": str(imported), "python": sys.executable,
          "prefix": sys.prefix}, sort_keys=True))
    executable = shutil.which("doc-atlas")
    assert executable, "installed doc-atlas console script not found"
    assert Path(executable).resolve().is_relative_to(Path(sys.prefix).resolve()), "console script must belong to the same isolated wheel environment"
    # The member policy rejects group-writable /tmp/opencode ancestors. A
    # private disposable directory below the user's secure home is authorized
    # fixture storage; no live configuration/index is opened or changed.
    with tempfile.TemporaryDirectory(prefix=".docatlas-release-smoke-", dir=Path.home()) as raw:
        root = Path(raw)
        env = isolated_environment(root)
        config_path = root / "user-home" / "opencode.json"
        register_server(AgentTarget("opencode", config_path, "json_opencode_mcp"))
        registrations = json.loads(config_path.read_text())["mcp"]["servers"]
        assert set(registrations) == {"docatlas"}, registrations
        entry = registrations["docatlas"]
        assert "enabled" not in entry and not entry.get("disabled"), entry
        blockers = []
        for text_only in (False, True):
            mode_root = root / ("text" if text_only else "structured")
            mode_root.mkdir(mode=0o700)
            mode_env = isolated_environment(mode_root)
            database = Path(mode_env["DOCATLAS_HOME"]) / "mcp-members" / "members.db"
            project = mode_root / "project"
            project.mkdir()
            (project / "README.md").write_text(
                f"# Docs MCP server\n\nThe command that starts the Docs MCP server is `{NEEDLE}`.\n", encoding="utf-8")
            _accept_fixture(project)
            params = StdioServerParameters(command=executable, args=entry["command"][1:],
                env={**mode_env, **(entry["environment"] if text_only else {})}, cwd=str(mode_root))
            prepared = None
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    await read_only_delivery(session, project, text_only=text_only)
                    assert not database.parent.exists(), "read-only request provisioned member storage"
                    if not read_only:
                        try:
                            prepared = await indexed_delivery(session, project, database, text_only=text_only)
                        except Exception as exc:
                            blockers.append(f"{'text' if text_only else 'structured'} cold preparation failed: {type(exc).__name__}: {exc}")
            if prepared is not None:
                try:
                    # Cold prepare/retrieve has already succeeded. Preload only
                    # the local library fixtures in that same isolated registry.
                    libraries = bootstrap_library_fixture(project, database.parent / "docs-indexes", database=database)
                    async with stdio_client(params) as streams:
                        async with ClientSession(*streams) as session:
                            await session.initialize()
                            await repeat_preparation(session, project, database, *prepared, text_only=text_only)
                            blockers.extend(await prepared_delivery_matrix(session, project, database, libraries,
                                             text_only=text_only, include_large=True))
                except Exception as exc:
                    blockers.append(f"{'text' if text_only else 'structured'} restarted matrix failed: {type(exc).__name__}: {exc}")
        assert not (root / "user-home" / ".docmancer").exists()
        if blockers:
            raise RuntimeError("BLOCKED full installed delivery matrix: " + "\n".join(blockers))
    if read_only:
        print("Installed read-only stdio delivery: PASS (structured/text, cold rejection, unauthorized fields). "
              "Indexed lifecycle/partial/complete/>32KB/scope/version NOT RUN.")
    else:
        print("Docs MCP installed-artifact stdio smoke: PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args()
    asyncio.run(smoke(read_only=args.read_only))
