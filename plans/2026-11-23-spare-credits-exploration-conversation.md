# Spare-Credits Exploration: Conversation

The brainstorm behind [2026-11-23-spare-credits-exploration.md](2026-11-23-spare-credits-exploration.md),
kept as a reference. User messages are verbatim; Claude's replies are recorded as sent, without
tool output.

## 1. User (2026-11-23)

> Since we have spare credits we're going to be spending them on something fun.  You'll be in
> charge of your own agents, and you can spend as much as you want to explore this space.  I
> have a couple of requirements.  We're going to be in plan mode for a bit.  Be sure to make a
> new branch, and then in that branch add a plan to plans/ and also save this conversation along
> side the plan so it can be used as a reference, including this message.

## 2. Claude

Made the branch `docs/spare-credits-exploration-plan` (from `origin/main` at `d5ae3fff`, in the
worktree `../glitchygames-spare-credits-plan`), added this plan skeleton and this conversation
record to `plans/`, and asked what the "something fun" is: whether a new game, a
toy, an engine experiment, or something outside the codebase, since that decides what the
agents go explore and where the work lives.

## 3. User (2026-11-23, sent while Claude was working)

> Make sure to pull the latest main

## 4. Claude

Fetched `origin` again: `origin/main` is still `d5ae3fff`, the commit the branch started from,
so the branch already has the latest main. The shared `glitchygames/` checkout was left alone;
the work stays in this branch's own worktree.

## 5. User (2026-11-23)

> I have the beginnings of an idea for a video game that I want to make that would be similar to
> "Slime Forest Adventure" in concept - that is a game that helps someone learn Japanese.  You
> can research it, but none of your research can be committed, so put it in ~/Documents or
> something - and don't reference the local path in the repoistory documentation, just refer to
> the ideas in general when collaborating with me on the ideas.  https://lrnj.com/

## 6. Claude

Started three research agents in parallel, with their notes kept outside the repository: one on
how Slime Forest Adventure weaves kana and kanji practice into RPG combat (and what players
praise and miss) plus a survey of other Japanese-learning games; one on the learning science
(spaced repetition, recall vs. recognition, kanji learning order, motivation in learning games)
and on openly licensed Japanese data, fonts and voices; and one on what the glitchygames engine
already offers for such a game (Japanese text rendering, text input, RPG building blocks, saves).
Noted that the goal is an original game that shares the concept, not a remake of that one.
Asked what drew the user to the idea and who the game is for.

## 7. Claude (research update)

The first research pass came back, on Slime Forest Adventure and similar games. In general terms:

- **Its core idea:** the combat action is the study action. You attack by typing the reading or
  meaning of the character over the enemy. A miss costs health and shows the answer, often with
  a memory hint.
- **Structure:** hiragana, then katakana, then about 2,000 kanji. Each dungeon works as a
  lesson and its test, since new characters are introduced only when the next area tests them.
  Kanji come in an order where every memory hint refers only to kanji already learned.
- **Review:** a simple custom review queue, not a published spaced-repetition method.
- **What players miss:** audio most of all, then sentences and grammar, compound words, stroke
  order and writing, and a visible review schedule. They also find the art and the game side
  thin.
- **The opening:** no game found combines typed recall, audio, writing, reading sentences and a
  visible review schedule in one loop.
- **Correction:** Claude's own research brief named the wrong developer; the official site names
  Darrell Johnson.
