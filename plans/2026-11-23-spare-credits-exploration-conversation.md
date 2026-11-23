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

## 8. Claude (research update)

The engine survey came back. What a Japanese-learning game would need that the engine lacks:

- **A font that draws Japanese:** only a Latin font is bundled. A full Japanese font is several
  megabytes, which matters for the browser build. A trimmed font (only the characters the game
  uses) or a pixel font would solve it.
- **Japanese typing:** the engine receives the operating system's text-input events but no
  widget uses them. Converting typed romaji to kana inside the game would avoid depending on the
  player's own input method, and would work the same in replays and the browser.
- **Building blocks for an RPG:** no tile maps, dialog boxes, battle system or overworld yet.

What it already has that fits:

- **Saves** that write atomically, where the review schedule would live.
- **Recording and replay** with seeded randomness, so a run (including which characters were
  asked) replays exactly.
- **Synthesized audio, sprites, scenes, transitions and the camera.**
- **Speech:** a desktop-only text-to-speech path.
- **Existing games to start from**, for title screens, HUD text and grid worlds.

## 9. User (2026-11-23)

> So our game isn't necessarily going to be exactly like slime forest adventure - in fact - I
> don't want to borrow most of the ideas - I just want to use it conceptually to start talking
> about my actual idea, which should have its own look and feel.  Something more akin to a FF6 or
> Chrono Trigger vibe in terms of gameplay - as a starting point to start thinking about the
> game's framing and as a lede to start the conversation.

## 10. Claude

Played it back: Slime Forest Adventure was only the opening reference ("a game that teaches
Japanese"), not a source of mechanics; the game gets its own look and feel, and its feel as a
game starts from the 16-bit console RPG era (story, party, exploration, menu-driven battles),
in its own world rather than a remake of any one game. Asked the user to describe their actual
idea in their own words.

## 11. Claude (research update)

The learning-science pass came back. It was written from the agent's own knowledge without live
lookups, so Claude started a second agent to check its license and citation claims against
primary sources. The ideas likely to matter whatever the game's shape:

- **Scheduling reviews:** use a modern spaced-repetition scheduler (FSRS). It estimates how
  likely the player is to remember each item right now, so reviews can happen whenever play
  brings them up, not on a daily deck.
- **Grading:** the game grades the player's answers itself (wrong, needed a hint, correct, fast
  and correct); the player never rates their own recall.
- **What counts as a strong review:** typed or spoken recall builds memory more than picking from
  choices; always show the answer after a miss; mix look-alike characters only once each has
  been learned on its own.
- **Motivation:** learning works best when it is the core action of the game, not a quiz for
  rewards. Aim for about 80-90% success. No time pressure on new items. Failing costs the game
  something (health, items), never learning progress.
- **Open data and fonts:** dictionaries, kanji data, stroke-order data, example sentences and
  Japanese fonts are openly licensed, some with share-alike terms. Synthesized Japanese voices
  are the riskiest area for licensing.

## 12. User (2026-11-23)

> Ok, next part... RPG with a really amazing skill tree.  I'll explain the tree's contents a bit
> later.  I just want you to come without pre-conceived notions until I'm ready to tell you.

## 13. Claude

Noted the skill tree as central, held off on any guesses or research about what it contains, and
invited the next part.

## 14. User (2026-11-23)

> And I see you're trying to ask me questions.  Can you give me the current list and I'll answer
> each.

## 15. Claude

Listed the open questions (none about the skill tree's contents):

1. Why this game, and who is it for?
2. Where does a player start in Japanese, and how far should the game take them?
3. What is the story or situation?
4. Where does the learning happen in play?
5. Which parts of Japanese are in scope?
6. How does the player answer?
7. Where does it run, and with what controls?
8. What should it look and sound like?
9. How big is the first version, and what does success look like?
10. What would make it a failure even if it technically works?
11. Where does it live: a game inside glitchygames, or its own project?
12. Does it have a name yet?

## 16. User (2026-11-23)

> 1. I'll answer this after we get the framework sorted to my liking.  2. It's not going to be
> about Japanese at all.  I'll explain later.  3. I'll explain later.  4. This is a good
> question, and one that I'm still considering.  5. Strike this question altogether.  6. Strike
> this question altgoether. 7. Let me think about this one.  8. Let me think about this one.  9.
> I have an answer for this, but I want to explain things in my own way before I answer this.
> 10. Let me think about this.  11. I'm not sure yet.  12. Not yet.  Let me finish my
> explanation for you of the sort of mechanistic parts, and then I'll describe what I'm sort of
> going for.

## 17. Claude

Rewrote the plan's intent: the game is not about Japanese; Slime Forest Adventure stays only as
the opening reference. Added a table of the open questions with the user's status for each,
struck 5 and 6, and invited the user to continue with the mechanics.

## 18. User (2026-11-23)

> Ok, so it's a language learning game, but not for Japanese at all.  There will be a time-loop
> component that is somehow wired with the different learning mechanisms in a gamified way.
> Repetition, etc... will happen through a sort of time-loop system where the player has to
> re-play the game but as they play the game I want to evoke a feeling of discovery for meaning
> and learning.  The feeling I get is like... metaphorically (or literally, it is a fantasy RPG,
> but I'm talking somewhat exepliarily in these examples) a grayscale world devoid of color... a
> hero arc where discovery/happenstance/curiosity/something climactic - as many JRPGs do; with
> grand music, cutscenes, drama, etc... - that unfolds into a rediscovery of a dying language
> that had all but disappeared from the world, hints to the reasons why - but a mysteriousness
> and curiosity and magicalness about the power of words, culture, and a feeling of
> connectedness to and completely different way of seeing the world.

## 19. Claude

Played back the time loop as the repetition engine, discovery of meaning as the feeling, the
grayscale world, the hero arc and the dying language. Asked whether the dying language is one
invented for the game or a real one.

## 20. User (2026-11-23)

> The time loop should be a very pragmatic and functional part of the world.  In fact, this would
> be the first feature we'd utilize AI as an integral part for.  For now, just record that AI will
> be integral to the gameplay intricacies and storytelling aspects of this game.

## 21. Claude

Recorded it in the plan without elaborating: the time loop is a pragmatic, functional part of the
world; it is the first feature to use AI as an integral part; AI is integral to the gameplay
intricacies and the storytelling.

## 22. User (2026-11-23)

> Think... dynamic skill tree that doesn't have fixed nodes (for language discovery in an organic
> manner, just like one would experience in a real, truly immersive scenario.  AI would help steer
> things, design the skill tree mechanics and emergent properties, ask clarifying questions, test
> possibilities, etc...

## 23. Claude

Recorded the dynamic skill tree. Asked whether the AI's role (steering, designing the tree's
mechanics and emergent properties, asking clarifying questions, testing possibilities) happens
while the game is being made, while it is being played, or both. Flagged that the engine today
turns the AI service off in replays and the browser, and that replays need exact repeats, so AI
during play would have its answers recorded like any other input.

## 24. User (2026-11-23)

> Likely both - it's part of what we'll need to research, consider, test, brainstorm.

## 25. Claude

Recorded it: AI likely plays a part both while the game is made and while it is played, and
where exactly is an open area to research, consider, test and brainstorm. Invited the user to
continue.

## 26. User (2026-11-23)

> Do you have any new questions other than the ones that I deferred?

## 27. Claude

Listed the new questions:

13. Is the language real or invented for the game? (asked earlier, still open)
14. Does the player walk away knowing a real language?
15. What carries over from one loop to the next?
16. Is the language spoken, written, or both?
17. Is the gray world literal on screen?
18. One player, or more?

## 28. User (2026-11-23)

> 13.  It's real.  I'll tell you at the end.  14. The point of the game is to help with
> acquisition through immersion in a simulated environment, rather than something particularly
> chunky and static - which is sort of how lrnj feels - but the game is still super useful and I
> see why they did it that way - I want something a bit more of an immersion situation, but very
> fun - or rather even addictive feeling.  There will need to be the right amount of
> tension/frustration and success/exhilaration.  15. Remember this for later - make sure you've
> recorded all of the deferrals and re-ask me when I signal you to later on.  16. Both.  Yes.  17.
> I think we should play around with it, but it need not be the only idea.  This is meant to be a
> creative brainstorming session where we'll make a bunch of small demos and feel things out.
> 18. Single player, but give some thought to situations where multi-player could improve
> playability and addictiveness.

## 29. Claude

Recorded the answers in the plan, gathered every deferred question into one table to re-ask when
the user signals, and noted small demos as the way to feel things out.

## 30. User (2026-11-23)

> Ok, again, just brainstorming so ideas welcome.  The notion is the language has been lost to
> time.  Hardly anybody outside of the country knows about it and their information is corrupted
> - like an unkind game of telephone where either through strife, or intentional cultural
> annihalation, a language - the pain of that - the hurt of the psyche - means that even the
> ancestors of those who were displaced and lost to time, deny the truth of what happened to
> them.  This could be demonstrated as animosity in the game with a dark cloud forming around a
> character that the hero of the story has some deep emotional connection to their ancestry - we
> can fill in the backstory later - that they are attuned to being able to "sense" - in a loose
> way - through sight, hearing thoughts of others, magic, etc etc etc. and that starts to weave
> the story and game mechanics together.  So this language would have very few native speakers
> left, knowledge outside of the very small communities would be corrupted or misguided and
> slowly over time the language fades from existence... we could show, for instance a vinette or
> in-engine video (replay or what have you) of time passing and the language fading from
> existence and with it, the color fading from the world ( just one example - we should be very
> open minded about alternative ideas altogether.) And through some set of circumstances - for
> example, I have one very specific idea that we could try out that would be super fun if it
> worked... I'll tell you in a moment.

## 31. Claude

Played back the lost language, the corrupted "telephone game" knowledge, the denial carried by
descendants shown as a dark cloud, the hero's attunement, and the vignette of the language and
color fading. Offered a few brainstorm ideas, marked as Claude's:

- **Garbled speech that clears up:** speech in the language shows as distorted script and
  muffled sound, and comes into focus as the player learns it. The game's own "telephone game"
  corruption becomes something the player sees and hears.
- **Wrong clues to sort out:** what outsiders tell the hero about the language is partly wrong.
  The tension comes from finding out which "facts" are corrupted, by checking them against the
  few people who really speak it.
- **The cloud reacts to language:** using the right word, gently, at the right moment thins the
  dark cloud around a person; a clumsy or wrong use thickens it. Learning becomes a way of
  reaching someone.
- **The fading told by the replay engine:** the engine already records and replays play exactly.
  The fading vignette could be a replay of a living village that loses color and words as it
  plays, and later loops could replay the player's own earlier runs as "echoes".
- **Respect for the real people:** because the language is real and the story touches real
  harm, the research should include how to portray it with the community's voice.

Then waited for the user's specific idea.

## 32. User (2026-11-23, sent while Claude was working)

> Are you getting the general idea?  In this one particular brianstorming session we can consider
> this color idea that I have, but we can try lots of things.

## 33. Claude

Confirmed the general idea in a few lines, treated the color idea as this session's one to
explore among many, and asked for the specific idea.
