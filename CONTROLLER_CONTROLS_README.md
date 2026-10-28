# Controller Controls for Bitmappy Multi-Controller System

This document provides a comprehensive guide to all controller controls and features in the Bitmappy multi-controller editing system.

## 🎮 **Multi-Controller System Overview**

The Bitmappy tool supports up to **4 simultaneous controllers** with independent navigation, editing, and visual distinction. Each controller is assigned a color in activation order (`MultiControllerManager.CONTROLLER_COLORS` in `src/apps/bitmappy/src/bitmappy/controllers/manager.py`):

- **1st activation**: Red (255, 0, 0)
- **2nd activation**: Green (0, 255, 0)
- **3rd activation**: Blue (0, 0, 255)
- **4th activation**: Yellow (255, 255, 0)

### **Controller Assignment Strategy**
- **Assignment**: A connected controller is assigned a controller ID on its first button press
- **Start Button Activation**: Press the Start button (in Film Strip Mode) to activate your controller and take the next color
- **Color "Stealing"**: Colors follow activation order, and every activation takes the next color (wrapping after Yellow), so pressing Start again re-colors your controller
- **Initial Position**: Controller indicators start on the first frame of the first filmstrip after activation

## 🔄 **Mode Switching System**

Controllers step through the editing modes with the analog triggers (`ModeSwitcher.handle_trigger_input` in `src/apps/bitmappy/src/bitmappy/controllers/modes.py`). A press is the trigger crossing 40% of its travel, with a 100 ms debounce:

### **Mode Switching Controls**
- **L2 Trigger**: Step forward: Film Strip -> Canvas -> R Slider -> G Slider -> B Slider -> Film Strip
- **R2 Trigger**: Step back: B Slider -> G Slider -> R Slider -> Canvas -> Film Strip (R2 does nothing in Film Strip Mode)
- **L2 + R2 together**: L2 wins (there is no chord)

### **Available Modes**
1. **Film Strip Mode** (Default) - Frame and animation navigation
2. **Canvas Mode** - Pixel editing and painting
3. **Slider Mode** - Color adjustment (R, G and B slider modes)

## 📱 **Film Strip Mode Controls**

*Default mode for frame and animation navigation*

### **Navigation Controls**
- **D-Pad Left**: Previous frame
- **D-Pad Right**: Next frame
- **D-Pad Up**: Previous animation
- **D-Pad Down**: Next animation
- **Left Shoulder (L1)**: Previous frame (alternative)
- **Right Shoulder (R1)**: Next frame (alternative)

### **Selection Controls**
- **A Button (Cross)**: Select current frame
- **Start Button**: Activate controller

### **Editing Controls**
- **B Button (Circle)**: Undo operation
- **X Button (Square)**: Redo operation (only when frame is visible)
- **Y Button (Triangle)**: Toggle onion skinning for selected frame

### **Visual Indicators**
- Colored triangle indicators show controller positions on film strips
- **Shared Frames**: Indicators on the same frame are drawn side by side, 8 pixels apart and centered above it (the keyboard's white triangle first, then Red, Green, Blue, Yellow)
- Independent scrolling and navigation per controller

## 🎨 **Canvas Mode Controls**

*Mode for pixel editing and painting*

### **Movement Controls**
- **D-Pad Left**: Start continuous movement left (hold for acceleration)
- **D-Pad Right**: Start continuous movement right (hold for acceleration)
- **D-Pad Up**: Start continuous movement up (hold for acceleration)
- **D-Pad Down**: Start continuous movement down (hold for acceleration)

### **Painting Controls**
- **A Button (Cross)**: Start/continue painting (drag to paint continuously; disabled while the selected frame is hidden)
- **B Button (Circle)**: Undo operation
- **X Button (Square)**: Redo operation (only when frame is visible)
- **Y Button (Triangle)**: Toggle selected frame visibility on canvas

### **Advanced Painting Controls**
- **Left Shoulder (L1)**:
  - **Without A**: Jump 8 pixels left (horizontal fill direction)
  - **With A**: Paint 8 pixels left (horizontal fill direction)
  - **Vertical fill direction**: Jump (or, with A, paint) 8 pixels up
- **Right Shoulder (R1)**:
  - **Without A**: Jump 8 pixels right (horizontal fill direction)
  - **With A**: Paint 8 pixels right (horizontal fill direction)
  - **Vertical fill direction**: Jump (or, with A, paint) 8 pixels down

### **Fill Direction**
- Each controller's fill direction is HORIZONTAL by default (`ControllerSelection.set_fill_direction`); no button toggles it yet

### **Visual Indicators**
- 50% transparent colored squares show controller positions on canvas
- Smart collision avoidance for overlapping indicators
- Real-time position tracking with undo/redo support

### **Canvas Rendering System**
- **Selected Frame**: Always draws at full opacity on top of the canvas
- **Onion Skinning**: May be enabled for easy back-and-forth comparison with other frames (Y in Film Strip Mode toggles it for the selected frame)
- **Triangle Button**: In Canvas Mode, Y hides or shows the selected frame so the onion skinning layers can be compared

## 🎨 **Slider Mode Controls**

*Mode for color adjustment and palette editing*

### **Slider Navigation**
- **D-Pad Up**: Navigate to previous slider (B → G → R)
- **D-Pad Down**: Navigate to next slider (R → G → B)

### **Slider Adjustment**
- **D-Pad Left**: Start continuous decrease (hold for acceleration)
- **D-Pad Right**: Start continuous increase (hold for acceleration)
- **Left Shoulder (L1)**: Start continuous decrease by 8 (hold for acceleration)
- **Right Shoulder (R1)**: Start continuous increase by 8 (hold for acceleration)

### **Other Buttons**
- **A, B, X, Y**: No action in slider mode (switch modes to undo or redo)

### **Available Sliders**
- **R Slider**: Red color component (0-255)
- **G Slider**: Green color component (0-255)
- **B Slider**: Blue color component (0-255)

### **Visual Indicators**
- Colored indicators show controller positions on sliders
- Real-time color well updates
- Independent slider control per controller

## ⌨️ **Keyboard Shortcuts**

*Additional keyboard controls for enhanced workflow*

### **General Controls**
- **Ctrl+Z**: Undo operation
- **Ctrl+Shift+Z** or **Ctrl+Y**: Redo operation
- **Ctrl+C / Ctrl+V**: Copy / paste the selected frame
- **Ctrl+Shift+Arrow Keys**: Pan the canvas
- **O**: Toggle global onion skinning on/off
- **Space**: Toggle animation play/pause

### **Navigation Controls**
- **Left / Right Arrows**: Previous / next frame
- **Up / Down Arrows**: Previous / next animation (previous / next slider while a controller is in Slider Mode)
- **0-9**: Select specific frame (0-9)

## 🔄 **Undo/Redo System**

### **Controller Position Undo/Redo**
- **Position Changes**: Undo/redo controller position movements
- **Mode Changes**: Undo/redo controller mode switches
- **Smart Tracking**: Continuous movements tracked as single operations
- **Shared History**: All controllers and the keyboard share one undo/redo history

### **Operation Types**
- **Pixel Changes**: Undo/redo pixel-level edits
- **Frame Operations**: Undo/redo frame additions, deletions, reordering
- **Animation Operations**: Undo/redo animation-level changes
- **Controller Operations**: Undo/redo controller positions and modes

## 🎯 **Advanced Features**

### **Collaborative Editing**
- **Multi-User Support**: Up to 4 simultaneous controllers
- **Independent Navigation**: Each controller operates independently
- **Conflict Resolution**: Smart handling of simultaneous edits
- **Real-Time Updates**: Live updates across all controllers

### **Visual Management**
- **Collision Avoidance**: Smart positioning for overlapping indicators
- **Mode-Based Rendering**: Show/hide indicators based on controller mode
- **Color Distinction**: Unique colors for each controller
- **Position Preservation**: Maintain positions when switching modes

### **Performance Optimization**
- **Efficient Rendering**: Optimized for multiple controllers
- **Memory Management**: Smart cleanup and resource management
- **Real-Time Tracking**: Minimal performance impact
- **Continuous Movement**: Smooth acceleration and deceleration

## 🐛 **Known Issues**

### **Minor Bugs (Livable but Annoying)**
- **Slider Continuous Movement**: Occasional issues with slider stopping on key release
- **Rapid Movement Tracking**: May occasionally miss very rapid controller movements
- **Mode Switching Edge Cases**: Complex controller interactions may have edge cases

### **Workarounds**
- **Slider Issues**: Release and re-press D-pad buttons if sliders don't stop
- **Movement Tracking**: Use deliberate movements for better tracking
- **Mode Switching**: Ensure triggers are fully pressed for reliable switching

## 🚀 **Future Improvements**

### **Planned Enhancements**
- **Enhanced Continuous Movement Detection**: Better detection of continuous movements
- **Improved Slider Handling**: More reliable slider button release handling
- **Undo/Redo Visualization**: Visual representation of undo/redo history
- **Performance Optimizations**: Further optimizations for high-frequency movements

### **Advanced Features**
- **Network Support**: Remote controller support
- **Cloud Collaboration**: Cloud-based collaborative sessions
- **Advanced Conflict Resolution**: More sophisticated conflict handling

## 📋 **Quick Reference**

### **Mode Switching**
- **L2**: Next mode (Film Strip -> Canvas -> R -> G -> B -> Film Strip)
- **R2**: Previous mode (B -> G -> R -> Canvas -> Film Strip)

### **Common Controls**
- **A**: Select/Paint (mode dependent)
- **B**: Undo (Film Strip and Canvas modes)
- **X**: Redo (Film Strip and Canvas modes, while the selected frame is visible)
- **Y**: Toggle features (mode dependent)
- **D-Pad**: Navigation/Movement
- **Shoulders**: Advanced navigation/Painting

### **Controller Colors** (in activation order)
- **1st**: Red
- **2nd**: Green
- **3rd**: Blue
- **4th**: Yellow

## 🔧 **Technical Details**

### **System Requirements**
- **Controllers**: Up to 4 simultaneous controllers
- **Input Support**: D-pad, analog sticks, triggers, face buttons, shoulder buttons
- **Visual System**: Triangles (film strip), 50% transparent squares (canvas) and circles (sliders), with collision avoidance
- **Undo/Redo**: Comprehensive operation tracking and history management

### **Performance Considerations**
- **Real-Time Updates**: Optimized for smooth performance
- **Memory Management**: Efficient resource usage
- **Collision Detection**: Smart positioning algorithms
- **Continuous Movement**: Acceleration and deceleration handling

---

*This document covers the complete controller control system for the Bitmappy multi-controller editing system. For technical implementation details, see the source code and test files.*
