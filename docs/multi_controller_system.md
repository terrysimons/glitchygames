# Multi-Controller System Documentation

## Overview

The Multi-Controller System enables up to 4 simultaneous controllers to navigate and interact with the bitmappy tool independently. Each controller has its own visual indicator, navigation state, and can operate simultaneously without conflicts.

## Features

- **Multi-Controller Support**: Up to 4 simultaneous controllers
- **Independent Navigation**: Each controller navigates film strips and frames independently
- **Visual Distinction**: Unique colored triangles for each controller (Red, Green, Blue, Yellow)
- **Smart Positioning**: Automatic collision avoidance when multiple controllers select the same frame
- **State Preservation**: Controllers maintain their selection state when switching between them
- **Hotplug Support**: Controllers can be connected/disconnected during operation

## Architecture

### Core Components

1. **MultiControllerManager** - Central singleton managing all controllers
2. **ControllerSelection** - Individual controller state management
3. **VisualCollisionManager** - Smart positioning and collision avoidance
4. **Integration with Bitmappy** - Event handling and film strip navigation

### Controller Color Scheme

- **Controller 0**: Red (255, 0, 0)
- **Controller 1**: Green (0, 255, 0)  
- **Controller 2**: Blue (0, 0, 255)
- **Controller 3**: Yellow (255, 255, 0)

## Usage Examples

### Basic Setup

```python
from glitchygames.tools.multi_controller_manager import MultiControllerManager
from glitchygames.tools.controller_selection import ControllerSelection
from glitchygames.tools.visual_collision_manager import VisualCollisionManager

# Initialize the system
manager = MultiControllerManager()
visual_manager = VisualCollisionManager()
controller_selections = {}

# Set up a controller
instance_id = 0
controller_id = manager.assign_controller(instance_id)
controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)
```

### Controller Activation

```python
# Activate a controller
controller_selections[controller_id].activate()
manager.activate_controller(instance_id)

# Set initial selection
controller_selections[controller_id].set_selection("animation_name", 0)

# Add visual indicator
visual_manager.add_controller_indicator(
    controller_id=controller_id,
    instance_id=instance_id,
    color=manager.CONTROLLER_COLORS[controller_id],
    position=(100, 100)
)
```

### Navigation

```python
# Navigate to different animation/frame
controller_selections[controller_id].set_selection("new_animation", 5)

# Get current selection
animation, frame = controller_selections[controller_id].get_selection()
print(f"Controller {controller_id} is at {animation}, frame {frame}")

# Get navigation history
history = controller_selections[controller_id].get_navigation_history()
for entry in history:
    print(f"Previous: {entry['animation']}, frame {entry['frame']}")
```

### Multi-Controller Navigation

```python
# Set up multiple controllers
for i in range(4):
    instance_id = i
    controller_id = manager.assign_controller(instance_id)
    controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)
    controller_selections[controller_id].activate()
    
    # Each controller can navigate independently
    controller_selections[controller_id].set_selection(f"animation_{i}", i)
    
    # Add visual indicators
    visual_manager.add_controller_indicator(
        controller_id=controller_id,
        instance_id=instance_id,
        color=manager.CONTROLLER_COLORS[controller_id],
        position=(100 + i * 50, 100)
    )

# All controllers can navigate independently
controller_selections[0].set_selection("animation_A", 0)
controller_selections[1].set_selection("animation_B", 1)
controller_selections[2].set_selection("animation_C", 2)
controller_selections[3].set_selection("animation_D", 3)
```

### Visual Collision Avoidance

```python
# Multiple controllers at same position
for i in range(3):
    visual_manager.add_controller_indicator(
        controller_id=i,
        instance_id=i,
        color=(255, 0, 0),
        position=(100, 100)  # Same position
    )

# System automatically applies offsets to prevent overlap
# Controller 0: (100, 100) - no offset
# Controller 1: (85, 85) - (-15, -15) offset
# Controller 2: (100, 100) - fallback offset
```

### Controller State Management

```python
# Check controller status
if manager.is_controller_active(instance_id):
    print(f"Controller {instance_id} is active")

# Get controller information
info = manager.get_controller_info(instance_id)
if info:
    print(f"Controller {info.controller_id}: {info.status.value}")

# Deactivate controller
controller_selections[controller_id].deactivate()
manager.deactivate_controller(instance_id)
```

### Hotplug Support

```python
# Handle controller connection
def on_controller_connected(instance_id):
    controller_id = manager.assign_controller(instance_id)
    if controller_id is not None:
        controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)
        print(f"Controller {controller_id} connected")

# Handle controller disconnection
def on_controller_disconnected(instance_id):
    if instance_id in manager.assigned_controllers:
        controller_id = manager.assigned_controllers[instance_id]
        if controller_id in controller_selections:
            del controller_selections[controller_id]
        print(f"Controller {controller_id} disconnected")
```

## Integration with Bitmappy

### Event Handling

```python
def handle_controller_event(event):
    """Handle controller events in bitmappy."""
    if event.type == pygame.CONTROLLERBUTTONDOWN:
        controller_id = event.instance_id
        
        if event.button == pygame.CONTROLLER_BUTTON_A:
            # A button - select current frame
            if controller_id in controller_selections:
                controller_selections[controller_id].activate()
                controller_selections[controller_id].set_selection("current_animation", 0)
                
        elif event.button == pygame.CONTROLLER_BUTTON_DPAD_LEFT:
            # D-pad left - previous frame
            if controller_id in controller_selections:
                current_animation, current_frame = controller_selections[controller_id].get_selection()
                if current_frame > 0:
                    controller_selections[controller_id].set_selection(current_animation, current_frame - 1)
                    
        elif event.button == pygame.CONTROLLER_BUTTON_DPAD_RIGHT:
            # D-pad right - next frame
            if controller_id in controller_selections:
                current_animation, current_frame = controller_selections[controller_id].get_selection()
                controller_selections[controller_id].set_selection(current_animation, current_frame + 1)
```

### Film Strip Integration

```python
def update_film_strip_indicators():
    """Update visual indicators on film strips."""
    for controller_id, selection in controller_selections.items():
        if selection.is_active():
            animation, frame = selection.get_selection()
            
            # Update visual indicator position
            if animation in film_strips:
                strip_position = film_strips[animation].get_frame_position(frame)
                visual_manager.update_controller_position(controller_id, strip_position)
```

## Advanced Features

### State Cloning

```python
# Clone controller state to another controller
source_controller = controller_selections[0]
target_controller = controller_selections[1]

source_controller.set_selection("animation_A", 5)
source_controller.clone_state_to(target_controller)

# Target controller now has same state
animation, frame = target_controller.get_selection()
assert animation == "animation_A"
assert frame == 5
```

### Navigation History

```python
# Track navigation history
controller = controller_selections[0]
controller.set_selection("animation1", 0)
controller.set_selection("animation2", 1)
controller.set_selection("animation3", 2)

# Get history
history = controller.get_navigation_history()
print(f"Navigation history: {len(history)} entries")
for entry in history:
    print(f"  {entry['animation']}, frame {entry['frame']}")
```

### Performance Optimization

```python
# Clean up inactive controllers
manager.cleanup_inactive_controllers()

# Optimize visual positioning
visual_manager.optimize_positioning()

# Clear all indicators
visual_manager.clear_all_indicators()
```

## Error Handling

### Invalid Operations

```python
# Handle invalid controller IDs gracefully
if not manager.is_controller_active(999):
    print("Controller 999 not found")

# Handle missing controller selections
if controller_id not in controller_selections:
    print(f"Controller {controller_id} not initialized")
```

### System Resilience

```python
# System handles rapid controller switching
for cycle in range(1000):
    for i in range(4):
        if i in controller_selections:
            controller_selections[i].set_selection(f"animation_{i}", cycle % 50)

# System handles controller disconnection/reconnection
for i in range(10):
    manager._handle_controller_connect(i)
    # ... use controller ...
    manager._handle_controller_disconnect(i)
```

## Best Practices

### 1. Controller Lifecycle Management

```python
def setup_controller(instance_id):
    """Properly set up a new controller."""
    controller_id = manager.assign_controller(instance_id)
    if controller_id is not None:
        controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)
        controller_selections[controller_id].activate()
        manager.activate_controller(instance_id)
        return controller_id
    return None

def cleanup_controller(instance_id):
    """Properly clean up a controller."""
    if instance_id in manager.assigned_controllers:
        controller_id = manager.assigned_controllers[instance_id]
        if controller_id in controller_selections:
            controller_selections[controller_id].deactivate()
            del controller_selections[controller_id]
        manager.deactivate_controller(instance_id)
```

### 2. Visual Indicator Management

```python
def update_controller_visuals():
    """Update all controller visual indicators."""
    for controller_id, selection in controller_selections.items():
        if selection.is_active():
            animation, frame = selection.get_selection()
            position = get_frame_position(animation, frame)
            visual_manager.update_controller_position(controller_id, position)
```

### 3. State Synchronization

```python
def sync_controller_states():
    """Synchronize controller states with UI."""
    for controller_id, selection in controller_selections.items():
        if selection.is_active():
            animation, frame = selection.get_selection()
            # Update UI elements
            update_film_strip_selection(controller_id, animation, frame)
            update_visual_indicator(controller_id, animation, frame)
```

## Troubleshooting

### Common Issues

1. **Controller not responding**
   - Check if controller is assigned: `manager.assigned_controllers`
   - Verify controller is active: `manager.is_controller_active(instance_id)`

2. **Visual indicators overlapping**
   - System automatically handles collision avoidance
   - Check collision groups: `visual_manager.collision_groups`

3. **State not preserved**
   - Ensure controller selection is activated: `selection.activate()`
   - Check navigation history: `selection.get_navigation_history()`

### Debug Information

```python
# Get system status
print(f"Active controllers: {manager.get_active_controllers()}")
print(f"Visual indicators: {len(visual_manager.indicators)}")
print(f"Collision groups: {len(visual_manager.collision_groups)}")

# Get controller details
for instance_id, info in manager.controllers.items():
    print(f"Controller {info.controller_id}: {info.status.value}, color {info.color}")
```

## Future Extensions

The multi-controller system provides a foundation for:

1. **Collaborative Editing**: Multiple users editing simultaneously
2. **Advanced Visual Management**: Custom indicators and positioning
3. **Session Management**: Save/load controller configurations
4. **Permission Systems**: Master/slave controller relationships

## API Reference

### MultiControllerManager

- `assign_controller(instance_id)` - Assign a controller ID
- `activate_controller(instance_id)` - Activate a controller
- `is_controller_active(instance_id)` - Check if controller is active
- `get_controller_info(instance_id)` - Get controller information
- `get_active_controllers()` - Get list of active controllers
- `cleanup_inactive_controllers()` - Clean up inactive controllers

### ControllerSelection

- `activate()` - Activate the controller
- `deactivate()` - Deactivate the controller
- `set_selection(animation, frame)` - Set animation and frame
- `get_selection()` - Get current animation and frame
- `get_navigation_history()` - Get navigation history
- `clone_state_to(other)` - Clone state to another controller

### VisualCollisionManager

- `add_controller_indicator(controller_id, instance_id, color, position)` - Add visual indicator
- `remove_controller_indicator(controller_id)` - Remove visual indicator
- `update_controller_position(controller_id, position)` - Update indicator position
- `get_final_position(controller_id)` - Get final position with offsets
- `optimize_positioning()` - Optimize all indicator positions
