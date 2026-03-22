# Bitmappy Architecture Diagrams

See the rendered version in the [mkdocs documentation](docs/architecture/bitmappy.md).

## 1. Bootstrap & Main Loop

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

## 2. Class Hierarchy

```mermaid
classDiagram
    class EventManager {
        +process_events()
    }

    class GameEngine {
        +EVENT_HANDLERS dict
        +scene_manager SceneManager
        +start()
        +_initialize_event_managers()
    }

    class SceneManager {
        +active_scene Scene
        +screen Surface
        +dt float
        +start()
        +switch_to_scene()
        +_update_scene()
        +_process_events()
        +_render_scene()
        +_update_display()
    }

    class Scene {
        +all_sprites LayeredDirty
        +next_scene Scene
        +setup()
        +cleanup()
        +update()
        +render()
    }

    class BitmapEditorScene {
        +canvas AnimatedCanvasSprite
        +film_strips list
        +color_well ColorWellSprite
        +sliders list
        +undo_redo_manager UndoRedoManager
        +multi_controller_manager MultiControllerManager
        +setup()
        +on_key_down_event()
        +on_left_mouse_button_down_event()
        +on_left_mouse_drag_event()
        +on_controller_hat_motion_event()
    }

    class DirtySprite {
        +dirty int
        +image Surface
        +rect Rect
    }

    class RootSprite {
        +on_mouse_event()
    }

    class Sprite {
        +x int
        +y int
        +name str
        +parent Sprite
    }

    class AnimatedCanvasSprite {
        +pixels_across int
        +pixels_tall int
        +set_pixel_at()
        +_flood_fill()
        +show_frame()
    }

    class FilmStripSprite {
        +film_strip_widget FilmStripWidget
        +on_left_mouse_button_down_event()
    }

    class AnimatedSprite {
        +_animations dict
        +frame_manager FrameManager
        +set_animation()
        +set_frame()
        +update()
    }

    EventManager <|-- GameEngine
    EventManager <|-- SceneManager
    EventManager <|-- Scene
    Scene <|-- BitmapEditorScene
    DirtySprite <|-- RootSprite
    RootSprite <|-- Sprite
    Sprite <|-- AnimatedCanvasSprite
    Sprite <|-- FilmStripSprite
    Sprite <|-- AnimatedSprite
```

## 3. Event Flow

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

## 4. UI Layout & Component Wiring

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

## 5. Rendering Pipeline

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

## 6. Undo/Redo & Operations

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

## 7. Sprite Load/Save Pipeline

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

## 8. Multi-Controller System

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
