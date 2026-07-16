// Drives the disguise + secret entry + cached nav end-to-end on the watch simulator
// (CLAUDE.md §7, §9 M3 definition of done). Assumes the app synced the seeded bank
// on a prior launch, so subjects are already cached (zero-network nav).
import XCTest

final class TutorBankWatchUITests: XCTestCase {
    override func setUp() { continueAfterFailure = false }

    func testTimerDisguiseThenSecretEntryToCachedSubjects() throws {
        let app = XCUIApplication()
        app.launchArguments = ["-uitestReset"]
        app.launch()

        // 1. Landing screen is the study timer, stopped at zero.
        let timer = app.staticTexts["timerDisplay"]
        XCTAssertTrue(timer.waitForExistence(timeout: 10), "timer display should be visible")
        XCTAssertEqual(timer.label, "00:00")
        XCTAssertTrue(app.buttons["Start"].exists, "Start button should exist")
        attach(app, "01-timer-disguise")

        // 2. Timer actually counts.
        app.buttons["Start"].tap()
        let counting = NSPredicate(format: "label != %@", "00:00")
        expectation(for: counting, evaluatedWith: timer)
        waitForExpectations(timeout: 5)

        // 3. Secret entry: long-press the timer face opens the tutor UI (Browse tab).
        timer.press(forDuration: 1.4)
        // Cached subjects rendered the offline bank (assert on a row, robust to the
        // sheet + TabView nesting the nav-bar title sits inside).
        XCTAssertTrue(
            app.staticTexts["AJAVA"].waitForExistence(timeout: 6),
            "long-press should reveal the tutor Subjects list"
        )
        XCTAssertTrue(app.staticTexts["DAA"].exists, "DAA should be listed from cache")
        attach(app, "02-tutor-subjects")

        // 5. Navigation into a subject works (lands on its units screen).
        app.staticTexts["AJAVA"].tap()
        XCTAssertTrue(
            app.navigationBars["AJAVA"].waitForExistence(timeout: 5),
            "tapping a subject should push its units screen"
        )
        attach(app, "03-subject-units")
    }

    private func attach(_ app: XCUIApplication, _ name: String) {
        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.name = name
        shot.lifetime = .keepAlways
        add(shot)
    }
}
