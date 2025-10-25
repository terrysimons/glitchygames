# Controller Controls for Bitmappy Multi-Controller System

This document provides a comprehensive guide to all controller controls and features in the Bitmappy multi-controller editing system.

## 🎮 **Multi-Controller System Overview**

The Bitmappy tool supports up to **4 simultaneous controllers** with independent navigation, editing, and visual distinction. Each controller is automatically assigned a unique color:

- **Controller 0**: Red (255, 0, 0)
- **Controller 1**: Green (0, 255, 0)
- **Controller 2**: Blue (0, 0, 255)
- **Controller 3**: Yellow (255, 255, 0)

### **Controller Assignment Strategy**
- **Color "Stealing"**: Users can "steal" a color by quickly re-initializing multiple times before someone else can get their preferred color
- **Start Button Activation**: Press the Start button to activate your controller
- **Initial Position**: Controller indicators start on the first frame of the first filmstrip after activation

## 🔄 **Mode Switching System**

Controllers can switch between different editing modes using analog triggers:

### **Mode Switching Controls**
- **L2 Trigger (Full Press)**: Switch to **Canvas Mode** for pixel editing
- **R2 Trigger (Full Press)**: Switch to **Film Strip Mode** for frame navigation
- **L2 + R2 (Both Full Press)**: Switch to **Slider Mode** for color adjustment

### **Available Modes**
1. **Film Strip Mode** (Default) - Frame and animation navigation
2. **Canvas Mode** - Pixel editing and painting
3. **Slider Mode** - Color adjustment (R, G, B sliders)

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
- **Collision Avoidance**: Film strips use the collision avoidance system to merge indicators together when multiple controllers are active on the same frame
- Independent scrolling and navigation per controller

## 🎨 **Canvas Mode Controls**

*Mode for pixel editing and painting*

### **Movement Controls**
- **D-Pad Left**: Start continuous movement left (hold for acceleration)
- **D-Pad Right**: Start continuous movement right (hold for acceleration)
- **D-Pad Up**: Start continuous movement up (hold for acceleration)
- **D-Pad Down**: Start continuous movement down (hold for acceleration)

### **Painting Controls**
- **A Button (Cross)**: Start/continue painting (drag to paint continuously)
- **B Button (Circle)**: Undo operation
- **X Button (Square)**: Redo operation (only when frame is visible)
- **Y Button (Triangle)**: Toggle selected frame visibility on canvas

### **Advanced Painting Controls**
- **Left Shoulder (L1)**:
  - **Without A**: Jump 8 pixels left (horizontal fill direction)
  - **With A**: Paint 8 pixels left (horizontal fill direction)
  - **Vertical Mode**: Jump 8 pixels up (vertical fill direction)
- **Right Shoulder (R1)**:
  - **Without A**: Jump 8 pixels right (horizontal fill direction)
  - **With A**: Paint 8 pixels right (horizontal fill direction)
  - **Vertical Mode**: Jump 8 pixels down (vertical fill direction)

### **Fill Direction Controls**
- **Y Button (Triangle)**: Toggle fill direction between HORIZONTAL and VERTICAL
- **Left Stick Button**: Toggle fill direction (alternative)
- **Right Stick Button**: Toggle fill direction (alternative)

### **Visual Indicators**
- 50% transparent colored squares show controller positions on canvas
- Smart collision avoidance for overlapping indicators
- Real-time position tracking with undo/redo support

### **Canvas Rendering System**
- **Selected Frame**: Always draws at full opacity on top of the canvas
- **Onion Skinning**: May be enabled for easy back-and-forth comparison with other frames
- **Triangle Button**: Use Y button (Triangle) to toggle onion skinning layers visibility
- **Layer Management**: Switch to canvas mode to see active onion skinning layers

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

### **Editing Controls**
- **B Button (Circle)**: Undo operation
- **X Button (Square)**: Redo operation (only when frame is visible)
- **A Button (Cross)**: No action in slider mode

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
- **Ctrl+Shift+Z**: Redo operation
- **O**: Toggle global onion skinning on/off
- **Space**: Toggle animation play/pause

### **Navigation Controls**
- **Arrow Keys**: Navigate frames and animations
- **0-9**: Select specific frame (0-9)
- **Tab**: Switch between controllers (if implemented)

## 🔄 **Undo/Redo System**

### **Controller Position Undo/Redo**
- **Position Changes**: Undo/redo controller position movements
- **Mode Changes**: Undo/redo controller mode switches
- **Smart Tracking**: Continuous movements tracked as single operations
- **Controller-Specific**: Each controller maintains independent undo history

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
- **L2**: Canvas Mode
- **R2**: Film Strip Mode
- **L2+R2**: Slider Mode

### **Common Controls**
- **A**: Select/Paint (mode dependent)
- **B**: Undo
- **X**: Redo
- **Y**: Toggle features (mode dependent)
- **D-Pad**: Navigation/Movement
- **Shoulders**: Advanced navigation/Painting

### **Controller Colors**
- **Controller 0**: Red
- **Controller 1**: Green
- **Controller 2**: Blue
- **Controller 3**: Yellow

## 🔧 **Technical Details**

### **System Requirements**
- **Controllers**: Up to 4 simultaneous controllers
- **Input Support**: D-pad, analog sticks, triggers, face buttons, shoulder buttons
- **Visual System**: 50% transparent indicators with collision avoidance
- **Undo/Redo**: Comprehensive operation tracking and history management

### **Performance Considerations**
- **Real-Time Updates**: Optimized for smooth performance
- **Memory Management**: Efficient resource usage
- **Collision Detection**: Smart positioning algorithms
- **Continuous Movement**: Acceleration and deceleration handling

---

*This document covers the complete controller control system for the Bitmappy multi-controller editing system. For technical implementation details, see the source code and test files.*
