<!-- jay-publish:19573d62d633b1f7 -->
# I shipped a zero-dependency secret scanner. It flagged my own README.


**Title options**
- A 40-line secret scanner flagged my sponsor link as a high-entropy key
- Why I stopped trusting "length >= 40" as a secret-detection rule
- Three MIT CLIs that gate a release without installing a single package

---

I wanted a pre-merge check for leaked credentials that could run inside an
air-gapped CI runner. No SaaS, no agent, no `pip install`. So I wrote three
small stdlib-only Python tools: a secret scanner, a marketing-copy compliance
marker, and a combined release gate that emits one PASS/BLOCK verdict.

The embarrassing part: the generic fallback rule matched any base64-ish string
of 40+ characters. On the first CI run it flagged the sponsor URL in my own
README — Shannon entropy 4.363. A URL is high-entropy *and* completely public.

The fix had two parts. First, a minimum entropy threshold instead of length
alone. Second, a small context check: if the candidate is part of a URL, skip it
unless a real provider-specific pattern also fires. I then made the self-test
prove the distinction: the same random string appears twice, once standalone
and once inside a URL, and exactly one of them must be reported.

Three things I took from it:

1. A detector without a negative test is not a detector. "It found the fake
   key" is the easy half; "it ignored the lookalike" is the half that breaks
   in production.
2. False positives are a trust problem, not a tuning problem. One noisy gate
   and the whole team adds `--no-verify`.
3. Stdlib-only is a feature customers actually pay for. Nothing to install,
   nothing to audit, nothing leaves the runner.

All three repos are MIT with green Actions:
github.com/highLuo/toksentry · /fin-compliance · /release_gate

If you've shipped a similar gate, I'd like to hear how you handle entropy
lookalikes — base64 blobs, lockfile hashes, and test fixtures are still the
cases I watch most closely.

---
*No pitch, no CTA in the community post. The goal is to be seen and challenged.*
