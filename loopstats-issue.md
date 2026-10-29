## Summary

The infrastructure for decoy-loop statistics (`LoopStats`) is fully implemented on the mix/provider side and transmitted to the directory authorities. However, the authorities neither store nor aggregate these statistics in `onPostDescriptor`. As a result, the n−1 attack countermeasure described in the spec is effectively not active.

## Context

There is a branch `mix_decoy_stats_propagation` and an issue titled "Propagate decoy stats to dirauths". This report provides runtime evidence that the mix-side and transport layers are working, and pinpoints the exact missing piece on the authority side.

## Code references (confirmed in `main` / `v0.0.107`)

| Component | Location | Status |
|---|---|---|
| `loops.LoopStats` struct | `loops/loops.go:22` | defined |
| Loop generation & tracking | `server/internal/decoy/decoy.go:279`, `:459` | implemented |
| Stats calculation | `server/internal/decoy/decoy.go:139` (`GetStats`) | implemented |
| Signed upload contains `LoopStats` | `core/pki/descriptor_impl.go:55-63` | implemented |
| Transmission to dirauth | `authority/voting/client/client.go:1310` | implemented |
| **Reception at dirauth** | `authority/voting/server/wire_handler.go:690` (`onPostDescriptor`) | `signedUpload.LoopStats` is deserialized but **never read** |

## Runtime evidence

Testnet with `SendDecoyTraffic = true` on mixes and service nodes (gateways deliberately excluded). With a temporary `Noticef` log inserted after signature verification, `auth1` logged:

```
NOTI auth1: onPostDescriptor: node mix2 uploaded LoopStats for epoch 2474925 with 11 segments
NOTI auth1: onPostDescriptor: node mix5 uploaded LoopStats for epoch 2474925 with 11 segments
NOTI auth1: onPostDescriptor: node mix6 uploaded LoopStats for epoch 2474925 with 8 segments
NOTI auth1: onPostDescriptor: node servicenode4 uploaded LoopStats for epoch 2474925 with 18 segments
NOTI auth1: onPostDescriptor: node gateway5 uploaded LoopStats for epoch 2474925 with 0 segments
```

**Interpretation:**

- Mixes report 8–12 segments (the mix-pairs traversed by their loops)
- Service nodes report 18 segments (mix-pairs leading to this endpoint)
- Gateways report 0 segments (expected — gateways are not on loop paths)

The data arrives complete and plausible, but is discarded.

## What the spec requires (but is not implemented)

According to the "Propagation of mix decoy loop statistics" spec:

1. Authorities combine reports from individual nodes into a network health status.
2. Ratios at faulty nodes approach 0; at healthy nodes they approach 1.
3. Authorities arrive at a consensus decision about topology in the next epoch.
4. Nodes with abnormal ratios are labelled malfunctioning and removed from the consensus.

The spec also notes that anomalies may have to be discarded if the corresponding `sent_loops_A[p]` is small — i.e., ratios are not statistically reliable when only a few loops were sent.

## Suggested next steps (for a future PR)

1. Persist `signedUpload.LoopStats` per peer/epoch in the authority state.
2. Aggregate `SegmentRatios` across all reporting nodes.
3. Define a deterministic threshold (binomial/standard-deviation-based, as per spec).
4. Feed the result into topology generation so faulty nodes are excluded from the next epoch's consensus.

## Impact

Operators cannot detect n−1 attacks or malfunctioning nodes via decoy-loop statistics, even though all the data is already collected, signed, and transmitted. The feature is effectively a no-op on the authority side.
