/// Which frame of an animation is on screen after a given wall-clock time. Each frame shows for
/// exactly its duration (the engine's per-tick rounding is not simulated; see the spec).
public struct AnimationClock: Sendable {
    /// When each frame stops showing, in seconds from the start; durations that aren't positive
    /// finite numbers count as 0
    private let frameEnds: [Double]
    private let loop: Bool
    private let total: Double
    private let showingFrameCount: Int

    public init(durations: [Double], loop: Bool) {
        var elapsed = 0.0
        let usableDurations = durations.map { $0.isFinite && $0 > 0 ? $0 : 0 }
        frameEnds = usableDurations.map { duration in
            elapsed += duration
            return elapsed
        }
        self.loop = loop
        total = elapsed
        showingFrameCount = usableDurations.filter { $0 > 0 }.count
    }

    public func frameIndex(at elapsed: Double) -> Int {
        guard total > 0, elapsed > 0 else {
            return 0
        }
        if !loop, elapsed >= total {
            return frameEnds.count - 1
        }
        let timeInCycle = elapsed.truncatingRemainder(dividingBy: total)
        return frameEnds.firstIndex { $0 > timeInCycle } ?? frameEnds.count - 1
    }

    /// The next time after `elapsed` at which frameIndex changes; nil when it never will again.
    public func nextChange(after elapsed: Double) -> Double? {
        guard showingFrameCount > 1 else {
            return nil
        }
        let start = max(0, elapsed)
        if loop {
            // The first frame boundary strictly after start. Rounding can put start/total on
            // either side of a whole cycle, so look from the cycle before to the one after.
            let cycle = (start / total).rounded(.down)
            for cycleNumber in [cycle - 1, cycle, cycle + 1] {
                if let boundary = frameEnds.lazy.map({ cycleNumber * self.total + $0 }).first(where: { $0 > start }) {
                    return boundary
                }
            }
            return nil
        }
        // Without looping, the last frame stays: the end of the animation is not a change
        guard let end = frameEnds.first(where: { $0 > start }), end < total else {
            return nil
        }
        return end
    }
}
