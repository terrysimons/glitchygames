# Bitmappy Architecture

Bitmappy is GlitchyGames' pixel art editor. These diagrams show how it is wired up
through the engine, from bootstrap to rendering.

## Bootstrap & Main Loop

How Bitmappy starts up: entry point through `main()`, GameEngine initialization,
scene setup, and the four-phase main loop.

```mermaid
sequenceDiagram
    participant User
    participant main as main()
    participant GE as GameEngine
    participant SM as SceneManager (singleton)
    participant BES as BitmapEditorScene

    User->>main: uv run bitmappy
    main->>GE: GameEngine(game=BitmapEditorScene)
    GE->>GE: parse CLI args (Scene.args() + GameEngine.args())
    GE->>GE: pygame.init(), create display
    main->>GE: engine.start()
    GE->>BES: BitmapEditorScene(options=OPTIONS)
    GE->>GE: _initialize_event_managers()
    GE->>SM: scene_manager.switch_to_scene(game)
    SM->>BES: setup()
    BES->>BES: _setup_menu_bar()
    BES->>BES: _setup_canvas()
    BES->>BES: _create_film_strips()
    BES->>BES: _setup_color_well()
    BES->>BES: _setup_sliders()
    BES->>BES: _setup_managers()
    GE->>SM: scene_manager.start()

    loop Main Game Loop (while active_scene is not None)
        SM->>SM: dt = perf_counter delta
        SM->>BES: _update_scene()
        SM->>GE: _process_events()
        GE->>GE: pygame.event.get()
        GE->>SM: EVENT_HANDLERS[event.type](event)
        SM->>BES: on_*_event(event)
        SM->>SM: _render_scene()
        SM->>SM: _update_display()
        SM->>SM: _handle_frame_pacing(timer)
    end
```

## Class Hierarchy

### Event dispatch chain (how events reach your scene)

`EventManager` is the base class for `GameEngine`, `SceneManager`, and every
`Scene`. This shared base is why events can flow through all of them using the
same `on_*_event()` API.

**Inheritance** — all dispatch chain classes share the `EventManager` base:

```mermaid
flowchart LR
    EM["EventManager"] --- GE["GameEngine"]
    EM --- SM["SceneManager"]
    EM --- SC["Scene"]
    SC --- BES["BitmapEditorScene"]
```

**Event flow** — how an SDL event reaches your handler in Bitmappy:

```mermaid
flowchart TD
    SDL["SDL Event"] --> GE["GameEngine\nO#40;1#41; EVENT_HANDLERS lookup"]
    GE --> MGR["Event Manager\ne.g. MouseEventManager"]
    MGR -->|"updates state,\nsynthesizes events"| SM["SceneManager\nforwards to active_scene"]
    SM --> BES["BitmapEditorScene\n#40;the active scene#41;"]
    BES --> HANDLER["Your handler runs\non_left_mouse_drag_event#40;#41;"]
    BES --> STUB["No handler?\nCached stub, O#40;1#41; no-op"]
```

The `GameEngine` receives every SDL event and does an O(1) dict lookup to find
the right event manager. The event manager updates its internal state (button
tracking, axis values, drag detection) and may synthesize higher-level events
(drag, drop, chord). It then forwards to the `SceneManager`, which passes
everything to the `active_scene`. In Bitmappy, that's `BitmapEditorScene`,
which overrides handlers like `on_key_down_event()`,
`on_left_mouse_button_down_event()`, `on_left_mouse_drag_event()`, and
`on_controller_hat_motion_event()`. Events it doesn't override hit the cached
stubs — O(1) no-ops after their first occurrence.

### Sprite hierarchy (renderable objects)

`DirtySprite` is pygame's base for all sprites that support dirty-rect
rendering. GlitchyGames extends it through `RootSprite` → `Sprite` to add
mouse events, non-optional `image`/`rect`, and named parent tracking.

```mermaid
flowchart TD
    DS["DirtySprite\ndirty, image, rect"]
    DS --> RS["RootSprite\nmouse event support\nnon-optional image/rect"]
    RS --> SP["Sprite\nx, y, name, parent"]
    SP --> ACS["AnimatedCanvasSprite\npixels_across, pixels_tall\nset_pixel_at#40;#41;, show_frame#40;#41;"]
    SP --> FSS["FilmStripSprite\nfilm_strip_widget\non_left_mouse_button_down_event#40;#41;"]
    SP --> AS["AnimatedSprite\n_animations, frame_manager\nset_animation#40;#41;, set_frame#40;#41;"]
```

## Event Flow

How pygame events propagate through the system: from `pygame.event.get()` through
the `EVENT_HANDLERS` dispatch table, into specialized event managers, through the
scene manager, and finally into Bitmappy's scene and sprite handlers.

```mermaid
flowchart TD
    PG["pygame.event.get()"] --> GE["GameEngine.process_events()"]
    GE --> EH{"EVENT_HANDLERS[event.type]"}

    EH -->|KEYDOWN| KEM["KeyboardEventManager"]
    EH -->|MOUSEBUTTONDOWN| MEM["MouseEventManager"]
    EH -->|JOYHATMOTION| CEM["ControllerEventManager"]
    EH -->|DROPFILE| DEM["DropEventManager"]
    EH -->|WINDOWEVENT| WEM["WindowEventManager"]
    EH -->|FPSEVENT| GEM["GameEventManager"]

    KEM --> SM["SceneManager.on_key_down_event()"]
    MEM --> SM2["SceneManager.on_left_mouse_button_down_event()"]
    CEM --> SM3["SceneManager.on_controller_hat_motion_event()"]
    DEM --> SM4["SceneManager.on_drop_file_event()"]

    SM --> BES["BitmapEditorScene.on_key_down_event()"]
    SM2 --> BES2["BitmapEditorScene.on_left_mouse_button_down_event()"]
    SM3 --> BES3["BitmapEditorScene.on_controller_hat_motion_event()"]
    SM4 --> BES4["BitmapEditorScene.on_drop_file_event()"]

    BES -->|"Ctrl+Z"| UNDO["UndoRedoManager.undo()"]
    BES -->|"Ctrl+S"| SAVE["SaveDialogScene"]
    BES -->|"Arrow keys"| CANVAS["AnimatedCanvasSprite"]
    BES -->|"O key"| ONION["Toggle Onion Skinning"]

    BES2 -->|"Canvas area"| PIXEL["canvas.set_pixel_at(x, y, color)"]
    BES2 -->|"Ctrl+click"| FLOOD["canvas._flood_fill(x, y, color)"]
    BES2 -->|"Film strip area"| FRAME["FilmStripSprite: select frame"]
    BES2 -->|"Menu item"| MENU["MenuItem: dialog scene"]
    BES2 -->|"Slider area"| SLIDER["SliderSprite: adjust RGBA"]

    BES3 --> MCM["MultiControllerManager"]
    MCM -->|"Canvas Mode"| CPAINT["Canvas navigation/paint"]
    MCM -->|"Film Strip Mode"| FNAV["Frame navigation/select"]
    MCM -->|"Slider Mode"| SADJ["Slider adjustment"]
```

## UI Layout & Component Wiring

How the UI components are arranged on screen and how data flows between them.
Dotted lines show data flow; solid lines show scene transitions via `switch_to_scene`.

```mermaid
flowchart TB
    subgraph Screen["Display Surface"]
        subgraph MenuArea["Menu Bar - top 24px"]
            ICON["MenuItem: raspb icon"]
            NEW["MenuItem: New"]
            SAVE_M["MenuItem: Save"]
            LOAD_M["MenuItem: Load"]
        end

        subgraph MainArea["Main Area"]
            CANVAS_S["AnimatedCanvasSprite\npixel grid"]
            subgraph RightPanel["Right Side"]
                FS1["FilmStripSprite 1\ndefault animation"]
                FS2["FilmStripSprite 2\nwalk animation"]
                ARROWS["Scroll Arrows"]
            end
        end

        subgraph BottomArea["Bottom Controls"]
            CW["ColorWellSprite\ncurrent color"]
            SR["SliderSprite R: 0-255"]
            SG["SliderSprite G: 0-255"]
            SB["SliderSprite B: 0-255"]
            SA["SliderSprite A: 0-255"]
            INFO["TextSprite\nanim name, frame, dims"]
        end
    end

    CANVAS_S -.->|"show_frame()"| FS1
    FS1 -.->|"frame selected"| CANVAS_S
    CW -.->|"active color"| CANVAS_S
    SR & SG & SB & SA -.->|"RGBA values"| CW

    LOAD_M -.->|"switch_to_scene"| LDS["LoadDialogScene"]
    SAVE_M -.->|"switch_to_scene"| SDS["SaveDialogScene"]
    NEW -.->|"switch_to_scene"| NDS["NewCanvasDialogScene"]

    LDS -.->|"return to"| BES_RETURN["BitmapEditorScene"]
    SDS -.->|"return to"| BES_RETURN
    NDS -.->|"return to"| BES_RETURN
```

## Rendering Pipeline

The four phases of each frame tick. Dirty-rect optimization ensures only changed
regions are redrawn and pushed to the display.

```mermaid
flowchart TD
    TICK["Frame Tick"] --> UPDATE["1. _update_scene()"]
    UPDATE --> DT["Scene.update dt\naccumulate delta time"]
    DT --> ANIM["AnimatedSprite.update dt\nadvance frame timers"]
    ANIM --> FM["FrameManager.notify_observers\ntrigger frame change callbacks"]
    FM --> DIRTY1["FilmStripSprite.dirty = 1\nanimation preview changed"]

    TICK --> EVENTS["2. _process_events()"]
    EVENTS --> ROUTE["GameEngine routes via\nEVENT_HANDLERS dict - O(1) lookup"]
    ROUTE --> HANDLER["BitmapEditorScene handlers\nmodify sprites"]
    HANDLER --> DIRTY2["Sprite.dirty = 1\npixel changed / slider moved / etc."]

    TICK --> RENDER["3. _render_scene()"]
    RENDER --> LDG["LayeredDirty.draw screen"]
    LDG --> CHECK{"sprite.dirty?"}
    CHECK -->|"dirty=0"| SKIP["Skip - no redraw"]
    CHECK -->|"dirty=1"| REDRAW["Blit sprite.image\nto screen at sprite.rect"]
    CHECK -->|"dirty=2"| FORCE["Force full blit"]
    REDRAW --> RECTS["Collect changed rects"]

    TICK --> DISPLAY["4. _update_display()"]
    DISPLAY --> PUPDATE["pygame.display.update rects\nonly repaint changed regions"]
```

## Undo/Redo & Operations

How user actions flow through operation trackers into the central undo/redo stack.
Canvas operations are batched per drag with 0.1s debounce for efficiency.

```mermaid
flowchart LR
    subgraph UserActions["User Actions"]
        PAINT["Paint pixels"]
        FILL["Flood fill"]
        FSEL["Select frame"]
        FDEL["Delete frame"]
        CMOVE["Controller move"]
    end

    subgraph Trackers["Operation Trackers"]
        COT["CanvasOperationTracker\npixel-level, batched per drag"]
        FOT["FilmStripOperationTracker\nframe-level operations"]
        CAOT["CrossAreaOperationTracker\ncontroller positions"]
    end

    subgraph URM["UndoRedoManager"]
        STACK_U["Undo Stack"]
        STACK_R["Redo Stack"]
    end

    PAINT --> COT
    FILL --> COT
    FSEL --> FOT
    FDEL --> FOT
    CMOVE --> CAOT

    COT -->|"batch submit\n0.1s debounce"| STACK_U
    FOT -->|"submit"| STACK_U
    CAOT -->|"submit"| STACK_U

    STACK_U -->|"Ctrl+Z"| STACK_R
    STACK_R -->|"Ctrl+Y"| STACK_U
```

## Sprite Load/Save Pipeline

How sprites are loaded from TOML files, saved back, and imported via drag-and-drop.

```mermaid
flowchart TD
    subgraph Load["Load Path"]
        FILE_IN["sprite.toml"] --> SF["SpriteFactory.load_sprite()"]
        SF --> DETECT["detect_file_format()"]
        DETECT --> PARSE["Parse TOML config"]
        PARSE --> DECIDE{"Multi-frame?"}
        DECIDE -->|Yes| AS["AnimatedSprite\nwith _animations dict"]
        DECIDE -->|No| BS["BitmappySprite\nsingle frame"]
        AS --> CANVAS_L["AnimatedCanvasSprite\ndisplays frames"]
        BS --> CANVAS_L
    end

    subgraph Save["Save Path"]
        CANVAS_SAVE["AnimatedCanvasSprite"] --> SER["AnimatedSpriteSerializer"]
        SER --> VALIDATE["Validate pixel data\ndetect per-pixel alpha"]
        VALIDATE --> WRITE_TOML["Write TOML\ncolors + frames + animations"]
        WRITE_TOML --> FILE_OUT["output.toml"]

        CANVAS_SAVE --> PNG["Export PNG\npygame.image.save"]
        PNG --> FILE_PNG["output.png"]
    end

    subgraph DragDrop["Drag and Drop"]
        DROP_FILE["Dropped file"] --> EXT{"Extension?"}
        EXT -->|".toml"| SF
        EXT -->|".png"| PNG_LOAD["pygame.image.load()"]
        PNG_LOAD --> NEW_FRAME["Insert as new frame"]
    end
```

## Multi-Controller System

Up to 4 color-coded controllers can operate simultaneously. Each controller
independently switches between three modes using shoulder buttons.

```mermaid
flowchart TD
    subgraph Assignment["Controller Assignment"]
        CONNECT["Controller connected"] --> FIRST["First button press"]
        FIRST --> RED["Red - controller 0"]
        FIRST --> GREEN["Green - controller 1"]
        FIRST --> BLUE["Blue - controller 2"]
        FIRST --> YELLOW["Yellow - controller 3"]
    end

    subgraph Modes["Mode Switching per Controller"]
        FSM["Film Strip Mode\nR2 to enter"]
        CM["Canvas Mode\nL2 to enter"]
        SLM["Slider Mode\nL2+R2 to enter"]

        FSM -->|"Press L2"| CM
        CM -->|"Press R2"| FSM
        CM -->|"Press L2+R2"| SLM
        SLM -->|"Release L2 or R2"| CM
        FSM -->|"Press L2+R2"| SLM
        SLM -->|"Release L2 or R2"| FSM
    end

    subgraph FilmStripControls["Film Strip Mode Controls"]
        FS_NAV["D-pad: Navigate frames"]
        FS_SEL["A: Select frame"]
        FS_SW["L1/R1: Switch animation"]
    end

    subgraph CanvasControls["Canvas Mode Controls"]
        C_MOVE["D-pad: Move cursor"]
        C_PAINT["A: Paint pixel"]
        C_JUMP["L1/R1: Jump 8 pixels"]
    end

    subgraph SliderControls["Slider Mode Controls"]
        S_ADJ["D-pad: Adjust value"]
        S_JUMP["L1/R1: Adjust by 8"]
    end

    FSM --> FilmStripControls
    CM --> CanvasControls
    SLM --> SliderControls
```
