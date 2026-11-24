import QtQuick
import QtTest
import Quickshell
import "Plugin" as Pomo

ShellRoot {
  QtObject {
    id: fakeService
    property bool available: true
    property var state: ({status: "off", phase: "work", seconds: 1500})
    property string lastAction: ""
    function send(action) { lastAction = action }
    function retry() { lastAction = "retry" }
  }
  FloatingWindow {
    id: window
    visible: true
    implicitWidth: 440
    implicitHeight: 500
    Rectangle {
      id: capture
      anchors.fill: parent
      color: "#171218"
      Pomo.TimerControls {
        id: controls
        anchors.centerIn: parent
        width: 360
        service: fakeService
      }
    }
    TestCase {
      id: test
      name: "PomodoroControls"
      when: false
      function childNamed(item, name) {
        if (item.objectName === name) return item
        if (!item.children) return null
        for (var i = 0; i < item.children.length; i++) {
          var found = childNamed(item.children[i], name)
          if (found) return found
        }
        return null
      }
      function check(actual, expected) { if (actual !== expected) throw new Error(String(actual) + " != " + String(expected)) }
      function ensure(value) { if (!value) throw new Error("Expected true") }
      function test_actions() {
        var primary = childNamed(controls, "primaryAction")
        ensure(primary !== null)
        check(primary.text, "Включить")
        console.log("Click primary", primary.text)
        mouseClick(primary)
        check(fakeService.lastAction, "enable")
        fakeService.state = {status: "running", phase: "work", seconds: 1499}
        check(childNamed(controls, "countdown").text, "24:59")
        check(primary.text, "Пауза")
        console.log("Click primary", primary.text)
        mouseClick(primary)
        check(fakeService.lastAction, "pause")
        fakeService.state = {status: "paused", phase: "work", seconds: 1499}
        console.log("Click primary", primary.text)
        mouseClick(primary)
        check(fakeService.lastAction, "start")
        wait(100)
        var reset = childNamed(controls, "resetAction")
        mouseClick(reset)
        check(fakeService.lastAction, "reset")
        fakeService.state = {status: "ready", phase: "break", seconds: 300}
        controls.announcement = true
        wait(100)
        check(primary.text, "Начать")
        check(childNamed(controls, "countdown").text, "05:00")
        console.log("Click primary", primary.text)
        mouseClick(primary)
        check(fakeService.lastAction, "start")
        controls.announcement = false
        fakeService.state = {status: "off", phase: "work", seconds: 1500}
        fakeService.available = false
        ensure(!primary.enabled)
        fakeService.available = true
        primary.forceActiveFocus()
        fakeService.lastAction = ""
        keyClick(Qt.Key_Return)
        check(fakeService.lastAction, "enable")
      }
      function test_screenshot() {
        fakeService.state = {status: "off", phase: "work", seconds: 1500}
        if (!Quickshell.env("POMODORO_QA_CAPTURE")) return
        capture.grabToImage(function(result) {
          result.saveToFile(Quickshell.env("POMODORO_QA_CAPTURE"))
        })
        wait(150)
      }
    }
  }
  property bool awaitingEnglish: false
  Timer {
    interval: 1000
    running: true
    onTriggered: {
      try {
        test.test_actions()
        test.test_screenshot()
        console.log("PASS real QML mouse and keyboard actions")
        awaitingEnglish = true
        console.log("QA_AWAIT_ENGLISH")
      } catch (error) {
        console.error("FAIL UI test:", error)
        Qt.exit(1)
      }
    }
  }

  Timer {
    interval: 100
    repeat: true
    running: awaitingEnglish
    onTriggered: {
      var primary = test.childNamed(controls, "primaryAction")
      if (primary.text === "Enable") {
        console.log("PASS live language switch ru -> en")
        Qt.exit(0)
      }
    }
  }

}
