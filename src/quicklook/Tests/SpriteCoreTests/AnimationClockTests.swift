import Testing

@testable import SpriteCore

@Test func clockLoops() {
    let clock = AnimationClock(durations: [0.5, 0.25], loop: true)
    #expect(clock.frameIndex(at: 0) == 0)
    #expect(clock.frameIndex(at: 0.6) == 1)
    #expect(clock.frameIndex(at: 0.76) == 0)
    #expect(clock.frameIndex(at: 1.3) == 1)
}

@Test func clockStopsWithoutLoop() {
    let clock = AnimationClock(durations: [0.5, 0.25], loop: false)
    #expect(clock.frameIndex(at: 0.6) == 1)
    #expect(clock.frameIndex(at: 10) == 1)
    #expect(clock.nextChange(after: 10) == nil)
}

@Test func clockAllZeroStaysOnFirstFrame() {
    let clock = AnimationClock(durations: [0, 0, -1], loop: true)
    #expect(clock.frameIndex(at: 5) == 0)
    #expect(clock.nextChange(after: 5) == nil)
}

@Test func clockZeroDurationFrameIsSkipped() {
    let clock = AnimationClock(durations: [0.5, 0, 0.5], loop: true)
    #expect(clock.frameIndex(at: 0.6) == 2)
}

@Test func clockNextChange() {
    let clock = AnimationClock(durations: [0.5, 0.25], loop: true)
    #expect(clock.nextChange(after: 0.1) == 0.5)
    #expect(clock.nextChange(after: 0.5) == 0.75)
    #expect(clock.nextChange(after: 0.8) == 1.25)
}

@Test func clockSingleFrameNeverChanges() {
    let clock = AnimationClock(durations: [0.5], loop: true)
    #expect(clock.frameIndex(at: 3) == 0)
    #expect(clock.nextChange(after: 3) == nil)
}

@Test func clockNegativeElapsedIsFirstFrame() {
    let clock = AnimationClock(durations: [0.5, 0.25], loop: true)
    #expect(clock.frameIndex(at: -1) == 0)
}

@Test func clockNextChangeIsAlwaysLater() {
    // 0.1 + 0.2 is 0.30000000000000004, which used to make nextChange(after: 0.4) return 0.4
    let clock = AnimationClock(durations: [0.1, 0.2], loop: true)
    let next = clock.nextChange(after: 0.4)
    #expect(next != nil)
    #expect(next! > 0.4)
    #expect(abs(next! - 0.6) < 1e-9)
}

@Test func clockNextChangeAdvancesThroughManyCycles() {
    let clock = AnimationClock(durations: [0.1, 0.2, 0.3], loop: true)
    var time = 0.0
    for _ in 0..<1000 {
        let next = clock.nextChange(after: time)!
        #expect(next > time)
        time = next
    }
    // Three changes per 0.6 s cycle: 1000 changes is 333 cycles plus the 0.1 s first frame
    #expect(abs(time - 199.9) < 1e-6)
}

@Test func clockNonFiniteDurationsCountAsZero() {
    let clock = AnimationClock(durations: [.nan, 0.5, .infinity, 0.25], loop: true)
    #expect(clock.frameIndex(at: 0.6) == 3)
    #expect(clock.nextChange(after: 0.1) == 0.5)
}
