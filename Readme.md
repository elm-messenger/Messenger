# The Messenger Game Engine

Messenger is a 2D game engine with experimental concepts for Elm based on **[WebGL](https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API)**.

This repository is a CLI tool to create messenger project.
Main development is under several repositories:

- Core Messenger Elm library: [messenger-core](https://github.com/elm-messenger/Messenger-core)
- WebGL rendering in Elm: [elm-regl](https://github.com/elm-messenger/elm-regl), [elm-regl-js](https://github.com/elm-messenger/elm-regl-js)
- Extra Messenger Elm library: [messenger-extra](https://github.com/elm-messenger/Messenger-extra)
- Messenger templates: [messenger-templates](https://github.com/elm-messenger/messenger-templates)

Other repositories related to Messenger:

- Examples: [messenger-examples](https://github.com/elm-messenger/messenger-examples)
- Messenger documentation: [messenger-docs](https://github.com/elm-messenger/messenger-docs)

## Games made with Messenger

More than 60 games are made with Messenger:

- [Reweave](https://github.com/linsyking/Reweave)
- [2023 SilverFOCS Games](https://focs.ji.sjtu.edu.cn/silverfocs/project/2023/p2)
- [2024 SilverFOCS Games](https://focs.ji.sjtu.edu.cn/silverfocs/project/2024/p2)

Including various game types: RPG, Platformer, Puzzle game, Visual novel, Roguelike, multi-player.

## Cool Features

- Engine in a library. Messenger core is built in a library.
- Message (or event) based. Faster development cycle, easier to divide work.
- Functional, but OOP styled. Take advantages of both functional programming and OOP.
- Borrow concepts from OS design, such as kernel isolation, virtual machine, context switching.

## Conceptual Picture

![](docs/concept.png)

## Tutorial/Guide

https://elm-messenger.netlify.app/
