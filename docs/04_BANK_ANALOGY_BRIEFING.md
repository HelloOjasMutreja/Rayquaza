# The Bank Drop-Box: A Plain-Language Guide to Rayquaza's Findings

This document explains the entire Rayquaza project — what Kyber and Dilithium are, what a
timing leak is, and what each of the five confirmed findings actually means — using a single
running analogy. It is written so that anyone (a non-specialist relative, a new team member,
or an AI agent picking up context for the first time) can read it once and understand both
the project and the results without needing the underlying mathematics.

## The setup

Imagine a bank with a drop-box outside it. Anyone can walk up and post a sealed package into
the box. Only the bank manager, using a private key, can open the box and retrieve what is
inside. The moment the manager opens it, both the stranger who sent the package and the
manager end up holding the same secret — a shared password they will use to talk privately
afterward.

This whole mechanism is called a **KEM** — a Key Encapsulation Mechanism. Kyber (officially
renamed ML-KEM) is one specific design of this drop-box, built so that even a quantum
computer cannot pick the lock. Dilithium (ML-DSA) is a related but different mechanism —
instead of a drop-box, think of it as a wax seal the manager stamps onto outgoing documents
so recipients can verify they really came from the bank, and were not forged.

The lock itself — the mathematics — is believed to be unbreakable, even by a quantum
computer. Nobody in this project tried to pick that lock. What this project investigated is
something different: **does the person operating the box behave the same way every single
time, regardless of what is inside the package?**

## The stopwatch problem

Here is the entire idea in one sentence: if the manager takes a different amount of time to
process a genuine package than a forged one, a patient observer standing outside with a
stopwatch can learn the manager's secret key — without ever touching the lock.

This is called a **timing side-channel**. The observer cannot see inside the box. They can
only time how long the manager takes. If that time varies depending on hidden information
(the secret key, or values derived from it), repeating the timing measurement thousands of
times slowly reveals the secret, one fragment at a time.

Code that takes exactly the same time no matter what it is processing is called
**constant-time**. The entire purpose of this project was to take a real, modern drop-box
design (Kyber and Dilithium, as implemented in the widely-used `liboqs` library), deliberately
introduce small mistakes that break constant-time behavior, confirm with a real stopwatch that
each mistake actually leaks, and then test whether an AI system (Claude) could find these
mistakes by reading the blueprints — the way a real attacker eventually would.

## The five rooms we tested

Think of the manager's process for opening a package as a sequence of five small rooms they
walk through. In a perfectly built bank, the manager walks through every room at the exact
same pace regardless of what's happening inside. We went into each room and quietly altered
something so the manager's pace would change — then measured whether an outside observer
could detect it.

### LEAK-5 — The bouncer's ticket check

Before handing over the shared secret, the manager actually re-seals a copy of what they found
inside the package and compares it, character by character, against the original package that
arrived. Think of it as a bouncer checking your ticket by reprinting a second ticket from the
booking record and holding the two side by side.

The correct way to do this comparison is to check every single character, every time, even
after finding a mismatch early on — so the total time never depends on *where* a mismatch
occurs. We swapped this for the everyday "give up the instant you spot a difference" version
of the comparison. This is the real-world bug class called **KyberSlash1's cousin** — a
classic, well-documented mistake.

**Result: extremely strong leak (t = 78.93).** This was the most obvious giveaway of all five
— like a bouncer who blurts out "wait, that doesn't match!" the moment the first digit looks
wrong, instead of calmly checking the whole ticket regardless.

### LEAK-2 — Reading the decoded note

After unscrambling the package, the manager has to decide, value by value, whether each
fragment of the message means a "0" or a "1." The correct way does this with simple
arithmetic that behaves identically either way. We replaced it with an if-this-then-that
decision — effectively making the manager pause to think "is this a 0 or a 1?" instead of
applying a single uniform calculation.

Interestingly, just looking at which way the decision went wasn't enough to create a
measurable difference — modern processors are very good at guessing what a manager will do
next and pre-preparing for it. The leak only became measurable once we deliberately made the
manager's decisions unpredictable, so the processor's guesses failed regularly and the
thinking pause became visible.

**Result: very strong leak (t = -139.91).** One important nuance: when this same code is
compiled with stronger optimization settings (`-O2`), the compiler automatically rewrites the
if-this-then-that decision into the safe, uniform version — closing the leak without anyone
asking it to. This means real-world deployments built with standard optimization flags may
already be protected against this specific variant, which is itself a useful finding for the
paper.

### LEAK-4 — Tidying up the unscrambled numbers

After the manager runs the core unscrambling math, the resulting numbers occasionally need a
small correction — adding a fixed adjustment value if a number came out negative. We made the
manager check each of the 256 numbers in sequence and only apply the correction when needed,
rather than always performing an equivalent calculation on every number regardless.

**Result: very strong leak (t = -318.58).** The manager's total processing time for the whole
batch of 256 numbers measurably depended on how many of those 256 needed the correction — and
that count is tied to the secret key.

### LEAK-1 — The panic button's hesitation

Recall the panic button concept: if the re-sealed copy doesn't match the original package
(meaning it was a forgery), the manager is supposed to silently swap the real shared secret
for random noise before handing anything out — so an attacker watching the *output* can never
tell success from failure. The correct version does this swap using a uniform action that
runs identically either way.

We made the manager instead pause and ask "should I swap?" with an explicit yes/no decision.
This recreates a real, documented compiler-level bug class (sometimes called "clangover" in
the literature) where certain compiler behavior can quietly reintroduce exactly this kind of
hesitation even when the original programmer wrote safe code.

**Result: very strong leak (t = 74.74).**

### LEAK-3 — The sign of a hidden number, tested on real hardware

Deep inside the unscrambling math, intermediate numbers derived from the secret key can come
out positive or negative. We made the manager take a visibly different path — adding a fixed
"tax" value — whenever a number came out negative, rather than treating positive and negative
identically.

This leak needed to be tested on genuine ARM-family hardware (an AWS Graviton2 cloud server,
the same chip family used in real embedded and mobile cryptographic hardware) rather than
the everyday x86 laptop hardware used for the other four leaks, because chip-level timing
behavior differs by hardware family and a result on the wrong chip wouldn't be trustworthy.

**Result: the strongest and cleanest leak of all five (t = −3956.26).** The actual time
difference was tiny in absolute terms — about 2 nanoseconds, the positive-number path took
roughly 13.2 nanoseconds on average and the negative-number path took roughly 15.3 nanoseconds
— but it was so *consistent*, repeated across tens of thousands of measurements, that the
statistical confidence is about as high as this kind of measurement can ever get.

## What "t-stat" means, in plain terms

Every result above includes a number like `t = 78.93` or `t = -3956.26`. Don't worry about the
sign — it just indicates which direction the timing difference ran. The size of the number is
what matters: it answers "how confident are we that this timing difference is a real effect,
not just random noise in the measurement?" A t-stat of 2 or 3 is the bare minimum scientists
usually accept as meaningful. Every single leak in this project cleared that bar by a wide
margin — the smallest (LEAK-1, t = 74.74) is roughly 25 times stronger than the conventional
threshold, and the largest (LEAK-3) is over a thousand times stronger.

## All five rooms, side by side

| Leak | Plain-language description | Technical location | Confidence (t-stat) | Hardware tested |
|---|---|---|---|---|
| LEAK-1 | Panic-button swap hesitates instead of acting uniformly | `verify.c` cmov, if-branch | 74.74 | x86-64 |
| LEAK-2 | Reading the decoded note pauses to decide 0 or 1 | `poly.c` poly_tomsg rounding | -139.91 | x86-64 |
| LEAK-3 | A hidden number's sign changes the manager's path | `ntt.c` basemul, coefficient sign | -3956.26 | ARM (Graviton2) |
| LEAK-4 | Tidying up 256 numbers takes a visible shortcut | `indcpa.c` decrypt normalization | -318.58 | x86-64 |
| LEAK-5 | The bouncer gives up the instant a mismatch appears | `kem.c` FO transform compare | 78.93 | x86-64 |

## Why any of this matters

None of these five mistakes break the underlying mathematics — the lock on the drop-box
remains, as far as anyone knows, unbreakable even by a quantum computer. What this project
demonstrates is that the lock is not the weak point. The person operating the box is. Every
one of these five behaviors is a small, easy-to-make implementation mistake — the kind a
busy engineer might introduce without realizing it, or the kind a compiler might
*accidentally reintroduce* even after the original code was written safely.

The second half of the project asks a sharper question: if an AI system is handed the
blueprints of the drop-box and asked "where might the manager behave inconsistently," can it
find these same five mistakes — the way a real attacker eventually would, but faster and at
scale? That comparison, against both human-style reasoning and traditional brute-force
testing tools, is what the rest of Rayquaza is measuring.
