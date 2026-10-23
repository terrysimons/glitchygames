# Bitmappy Architecture

Bitmappy is GlitchyGames' pixel art editor. These diagrams show how it is wired up
through the engine, from bootstrap to rendering.

## Bootstrap & Main Loop

How Bitmappy starts up: entry point through `main()`, GameEngine initialization,
scene setup, and the main loop (one frame per pass, ended by `_finish_frame`).

```mermaid
sequenceDiagram
    participant User
    participant main as main()
    participant GE as GameEngine
    participant SM as SceneManager (singleton)
    participant BES as BitmapEditorScene

    User->>main: uv run bitmappy
    main->>GE: GameEngine(game=BitmapEditorScene, icon=...)
    GE->>GE: parse CLI args (GameEngine.args() + BitmapEditorScene.args())
    GE->>GE: pygame.init(), create display
    main->>main: load_ai_training_data()
    main->>GE: engine.start()
    GE->>BES: BitmapEditorScene(options=OPTIONS)
    BES->>BES: EditorSetup.init_undo_redo_system()
    BES->>BES: EditorSetup.setup_menu_bar()
    BES->>BES: EditorSetup.setup_canvas(options)
    BES->>BES: SliderManager.setup_sliders_and_color_well()
    BES->>BES: EditorSetup.setup_debug_text_box()
    BES->>BES: FilmStripCoordinator.setup_film_strips()
    GE->>GE: _initialize_event_managers()
    GE->>SM: scene_manager.switch_to_scene(game)
    SM->>BES: setup() (AIManager.setup() starts the AI worker)
    GE->>SM: scene_manager.start()

    loop Main Game Loop (while active_scene is not None)
        Note over SM: dt = the previous frame's start-to-start time
        SM->>SM: camera.begin_frame()
        SM->>BES: _update_scene() (Scene.dt_tick: logic and collision)
        SM->>GE: _process_events()
        GE->>GE: _pump_events() (active_sources().pump_events(): live, pygame.event.get())
        GE->>SM: EVENT_HANDLERS[event.type](event)
        SM->>BES: on_*_event(event)
        SM->>SM: _run_supervisor_slot() (supervisors, e.g. a recording's)
        SM->>SM: _update_frame_services() (shake, rumble)
        SM->>SM: _aim_active_camera() (camera_target / follow)
        SM->>SM: _position_active_world_sprites() (world sprites' rect, culling)
        SM->>SM: _render_scene() (BitmapEditorScene.update: animation, controllers, AI; then draw)
        SM->>SM: _advance_still_camera_shake() (WORLD shake nothing advanced)
        SM->>SM: _present_frame() (overlay, display update)
        SM->>SM: _finish_frame() (pace, then set dt once from perf_counter)
    end
```

## Class Hierarchy

### Event dispatch chain (how events reach your scene)

`EventManager` is the base class for `GameEngine` and `SceneManager`. Every `Scene` instead
inherits `AllEventStubs`, which gives it a default `on_*_event()` method for every event, so
events flow through all of them using the same `on_*_event()` API.

**Inheritance:**

```mermaid
flowchart LR
    EM["EventManager"] --- GE["GameEngine"]
    EM --- SM["SceneManager"]
    STUBS["AllEventStubs"] --- SC["Scene"]
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
    BES --> STUB["No handler?\nThe stub calls unhandled_event#40;#41;"]
```

The `GameEngine` receives every SDL event and does an O(1) dict lookup to find
the right event manager. The event manager updates its internal state (button
tracking, axis values, drag detection) and may synthesize higher-level events
(drag, drop, chord). It then forwards to the `SceneManager`, which passes
everything to the `active_scene`. In Bitmappy, that's `BitmapEditorScene`,
which overrides handlers like `on_key_down_event()`,
`on_left_mouse_button_down_event()`, `on_left_mouse_drag_event()`, and
`on_controller_button_down_event()`. Events it doesn't override hit the stubs, which call
`unhandled_event()`: it does nothing by default, logs each event type once when the log level
is DEBUG, ERROR or CRITICAL, and raises `UnhandledEventError` under `--no-unhandled-events` (as the tests
run).

### Sprite hierarchy (renderable objects)

`DirtySprite` is pygame's base for all sprites that support dirty-rect
rendering. GlitchyGames extends it through `RootSprite` → `Sprite` → `BitmappySprite` to add
mouse events, non-optional `image`/`rect`, named parent tracking and TOML load/save.
`AnimatedSprite` derives from `DirtySprite` directly.

```mermaid
flowchart TD
    DS["DirtySprite\ndirty, image, rect"]
    DS --> RS["RootSprite\nmouse event support\nnon-optional image/rect"]
    RS --> SP["Sprite\nx, y, name, parent"]
    SP --> BS["BitmappySprite\nload#40;#41;, save#40;#41;"]
    BS --> ACS["AnimatedCanvasSprite\npixels_across, pixels_tall\ncanvas_interface.set_pixel_at#40;#41;, show_frame#40;#41;"]
    BS --> FSS["FilmStripSprite\nfilm_strip_widget\non_left_mouse_button_down_event#40;#41;"]
    DS --> AS["AnimatedSprite\n_animations, frame_manager\nset_animation#40;#41;, set_frame#40;#41;"]
```

## Event Flow

How pygame events propagate through the system: from `GameEngine._pump_events()` (live:
`pygame.event.get()`) through
the `EVENT_HANDLERS` dispatch table, into specialized event managers, through the
scene manager, and finally into Bitmappy's scene and sprite handlers.

```mermaid
flowchart TD
    PG["GameEngine._pump_events()\nactive_sources().pump_events()"] --> GE["GameEngine.process_events()"]
    GE --> EH{"EVENT_HANDLERS[event.type]"}

    EH -->|KEYDOWN| KEM["KeyboardEventManager"]
    EH -->|MOUSEBUTTONDOWN| MEM["MouseEventManager"]
    EH -->|CONTROLLERBUTTONDOWN| CEM["ControllerEventManager"]
    EH -->|DROPFILE| DEM["DropEventManager"]
    EH -->|"WINDOW* events"| WEM["WindowEventManager"]
    EH -->|FPSEVENT| GEM["GameEventManager"]

    KEM --> SM["SceneManager.on_key_down_event()"]
    MEM --> SM2["SceneManager.on_left_mouse_button_down_event()"]
    CEM --> SM3["SceneManager.on_controller_button_down_event()"]
    DEM --> SM4["SceneManager.on_drop_file_event()"]

    SM --> BES["BitmapEditorScene.on_key_down_event()"]
    SM2 --> BES2["BitmapEditorScene.on_left_mouse_button_down_event()"]
    SM3 --> BES3["BitmapEditorScene.on_controller_button_down_event()"]
    SM4 --> BES4["BitmapEditorScene.on_drop_file_event()\nFileIOManager"]

    BES -->|"Ctrl+Z / Ctrl+Y, Ctrl+Shift+Z"| UNDO["handle_undo() / handle_redo()"]
    BES -->|"Ctrl+C / Ctrl+V"| COPY["Copy / paste frame"]
    BES -->|"Ctrl+Shift+Arrow"| PAN["Pan the frame's pixels"]
    BES -->|"Arrow keys, 0-9, Space"| CANVAS["AnimatedCanvasSprite.handle_keyboard_event()"]
    BES -->|"O key"| ONION["Toggle Onion Skinning"]

    BES2 -->|"Canvas area"| PIXEL["canvas.canvas_interface.set_pixel_at(x, y, color)"]
    BES2 -->|"Ctrl+click"| FLOOD["canvas._flood_fill(x, y, color)"]
    BES2 -->|"Film strip area"| FRAME["FilmStripSprite: select frame"]
    BES2 -->|"Menu item"| MENU["MenuItem: dialog scene"]
    BES2 -->|"Slider area"| SLIDER["SliderSprite: adjust RGBA"]

    BES3 --> CEH["ControllerEventHandler"]
    CEH --> MCM["MultiControllerManager\n(assigns the controller)"]
    CEH --> MS["ModeSwitcher strategy"]
    MS -->|"Canvas Mode"| CPAINT["Canvas navigation/paint"]
    MS -->|"Film Strip Mode"| FNAV["Frame navigation/select"]
    MS -->|"Slider Mode"| SADJ["Slider adjustment"]
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
                FS1["FilmStripSprite 1\nfirst animation"]
                FS2["FilmStripSprite 2\nsecond animation"]
                ARROWS["Scroll Arrows"]
                AI["TextSprite 'AI Sprite' +\nMultiLineTextBox (AI prompt, messages)"]
            end
        end

        subgraph BottomArea["Bottom Controls"]
            CW["ColorWellSprite\ncurrent color"]
            SA["SliderSprite A: 0-255"]
            SR["SliderSprite R: 0-255"]
            SG["SliderSprite G: 0-255"]
            SB["SliderSprite B: 0-255"]
        end
    end

    CANVAS_S -.->|"show_frame()"| FS1
    FS1 -.->|"frame selected"| CANVAS_S
    CW -.->|"active color"| CANVAS_S
    SR & SG & SB & SA -.->|"RGBA values"| CW
    AI -.->|"on_text_submit_event"| AIM["AIManager"]

    LOAD_M -.->|"next_scene"| LDS["LoadDialogScene"]
    SAVE_M -.->|"next_scene"| SDS["SaveDialogScene"]
    NEW -.->|"next_scene"| NDS["NewCanvasDialogScene"]

    LDS -.->|"return to"| BES_RETURN["BitmapEditorScene"]
    SDS -.->|"return to"| BES_RETURN
    NDS -.->|"return to"| BES_RETURN
```

## Rendering Pipeline

The steps of each frame, in order (`SceneManager._run_scene_frame`, then `_finish_frame`).
Bitmappy has no world-space sprites, so steps 5 and 6 leave its widgets alone. Dirty-rect
optimization ensures only changed regions are redrawn and pushed to the display.

```mermaid
flowchart TD
    BEGIN["1. camera.begin_frame()\nclear the camera's update and shake-advance flags"] --> LOGIC
    LOGIC["2. _update_scene()\nScene.dt_tick(dt): logic, animation, collision\n(dt capped by MAX_FRAME_SECONDS when set)"] --> EVENTS
    EVENTS["3. _process_events(), then _run_supervisor_slot()\nEVENT_HANDLERS dict - O(1) lookup\nBitmapEditorScene handlers modify sprites"] --> SERVICES
    SERVICES["4. _update_frame_services()\nshake and rumble"] --> AIM
    AIM["5. _aim_active_camera()\ncamera_target() / follow target\n(skipped when the scene was switched mid-frame)"] --> POSITION
    POSITION["6. _position_active_world_sprites()\nworld sprites' rect from the camera, culling\n(screen-space sprites untouched)"] --> RENDER
    RENDER["7. _render_scene()\nScene.update() (visual only), LayeredDirty.draw"] --> CHECK{"sprite.dirty?"}
    RENDER --> FM["BitmapEditorScene.update()\ncanvas.update_animation(dt)\nFilmStripCoordinator.update_film_strip_animation_timing()\nFilmStripSprite.dirty = 1 when a frame advances"]
    CHECK -->|"dirty=0"| SKIP["Skip - no redraw"]
    CHECK -->|"dirty=1 or 2"| REDRAW["Blit sprite.image at sprite.rect\ncollect changed rects"]
    SKIP --> STILL
    REDRAW --> STILL
    STILL["8. _advance_still_camera_shake()\nadvance a WORLD shake nothing advanced this frame\n(no aim, no game camera.update())"] --> PRESENT
    PRESENT["9. _present_frame()\ndebug overlay, pygame.display.update rects or flip"] --> FINISH
    FINISH["10. _finish_frame()\npace, then one perf_counter reading sets the next dt"]
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
        FCOPY["Copy/paste frame"]
        CMOVE["Controller move / mode change"]
    end

    subgraph Trackers["Operation Trackers"]
        COT["CanvasOperationTracker\npixel-level, batched per drag"]
        FOT["FilmStripOperationTracker\nframe-level operations"]
        CAOT["CrossAreaOperationTracker\nframe copy/paste"]
        CPOT["ControllerPositionOperationTracker\ncontroller positions and modes"]
    end

    subgraph URM["UndoRedoManager (max_history=50)"]
        STACK_F["Per-frame Undo/Redo Stacks"]
        STACK_U["Global Undo Stack"]
        STACK_R["Global Redo Stack"]
    end

    PAINT --> COT
    FILL --> COT
    FSEL --> FOT
    FDEL --> FOT
    FCOPY --> CAOT
    CMOVE --> CPOT

    COT -->|"batch submit\n0.1s debounce"| STACK_F
    FOT -->|"submit"| STACK_U
    CAOT -->|"submit"| STACK_U
    CPOT -->|"submit"| STACK_U

    STACK_F -.->|"Ctrl+Z tries the current frame first"| STACK_U
    STACK_U -->|"Ctrl+Z"| STACK_R
    STACK_R -->|"Ctrl+Y / Ctrl+Shift+Z"| STACK_U
```

## Sprite Load/Save Pipeline

How sprites are loaded from TOML files, saved back, and imported via drag-and-drop.

```mermaid
flowchart TD
    subgraph Load["Load Path"]
        FILE_IN["sprite.toml"] --> CLOAD["AnimatedCanvasSprite.on_load_file_event()"]
        CLOAD --> DETECT["detect_file_format()\n(glitchygames/bitmappy/utils.py: TOML only)"]
        DETECT --> AS["AnimatedSprite().load(filename)\nstatic sprites become one-frame animations"]
        AS --> CANVAS_L["AnimatedCanvasSprite\ndisplays frames, resizes to fit"]
    end

    subgraph Save["Save Path"]
        CANVAS_SAVE["AnimatedCanvasSprite.on_save_file_event()"] --> DECIDE{"One frame?"}
        DECIDE -->|Yes| STATIC["AnimatedSprite._save_as_static_sprite()"]
        DECIDE -->|No| SER["AnimatedSpriteSerializer\n-> AnimatedSprite.save()"]
        SER --> WRITE_TOML["Write TOML\ncolors (per-pixel alpha detected) + frames + animations"]
        STATIC --> FILE_OUT["output.toml"]
        WRITE_TOML --> FILE_OUT
    end

    subgraph DragDrop["Drag and Drop (FileIOManager)"]
        DROP_FILE["Dropped file"] --> WHERE{"Where?"}
        WHERE -->|"Film strip: image file"| FS_DROP["FilmStripSprite.on_drop_file_event()\non a frame: replace it\nelsewhere: insert a new frame"]
        WHERE -->|"Canvas: .toml"| CLOAD
        WHERE -->|"Canvas: .png"| CONVERT["_convert_png_to_bitmappy()\nPNG -> TOML"]
        CONVERT --> CLOAD
    end
```

## Multi-Controller System

Up to 4 color-coded controllers can operate simultaneously. Each controller
independently switches between film strip, canvas and slider (R, G, B) modes using the
triggers: L2 steps forward, R2 steps back (R2 does nothing in film strip mode). B undoes
and X redoes in film strip and canvas modes.

```mermaid
flowchart TD
    subgraph Assignment["Controller Assignment"]
        CONNECT["Controller connected"] --> FIRST["First button press\nMultiControllerManager.assign_controller()"]
        FIRST --> RED["Red - controller 0"]
        FIRST --> GREEN["Green - controller 1"]
        FIRST --> BLUE["Blue - controller 2"]
        FIRST --> YELLOW["Yellow - controller 3"]
    end

    subgraph Modes["Mode Switching per Controller (ModeSwitcher)"]
        FSM["Film Strip Mode\n(starting mode)"]
        CM["Canvas Mode"]
        SLM["Slider Modes\nR, then G, then B"]

        FSM -->|"L2"| CM
        CM -->|"L2"| SLM
        SLM -->|"L2 on B"| FSM
        SLM -->|"R2 on R"| CM
        CM -->|"R2"| FSM
    end

    subgraph FilmStripControls["Film Strip Mode Controls"]
        FS_NAV["D-pad left/right, L1/R1: Previous/next frame"]
        FS_ANIM["D-pad up/down: Previous/next animation"]
        FS_SEL["A: Select frame"]
        FS_ONION["Y: Toggle onion skinning"]
    end

    subgraph CanvasControls["Canvas Mode Controls"]
        C_MOVE["D-pad: Move cursor"]
        C_PAINT["A: Paint pixel"]
        C_JUMP["L1/R1: Jump 8 pixels\n(with A held: paint 8)"]
        C_VIS["Y: Toggle selected frame visibility"]
    end

    subgraph SliderControls["Slider Mode Controls"]
        S_ADJ["D-pad left/right: Adjust value"]
        S_NAV["D-pad up/down: Previous/next slider"]
        S_JUMP["L1/R1: Adjust by 8"]
    end

    FSM --> FilmStripControls
    CM --> CanvasControls
    SLM --> SliderControls
```
