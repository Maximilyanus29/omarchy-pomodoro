import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Commons as Commons
import qs.Ui

Item {
  id: root
  property var shell: null
  property var manifest: null
  property var state: ({status: "off", phase: "work", seconds: 1500, alert: false, serial: 0, error: ""})
  property bool available: false
  property bool alertOpen: false
  property int seenSerial: -1

  function send(action) {
    if (!available) return
    backend.write(JSON.stringify({action: action}) + "\n")
  }
  function dismiss() {
    alertOpen = false
    send("dismiss")
  }
  function retry() {
    if (!backend.running) backend.running = true
  }
  function accept(data) {
    try {
      var next = JSON.parse(data)
      if (["off", "running", "paused", "ready"].indexOf(next.status) < 0
          || ["work", "break"].indexOf(next.phase) < 0
          || typeof next.seconds !== "number" || next.seconds < 0) return
      state = next
      available = true
      if (next.alert && seenSerial !== next.serial) {
        seenSerial = next.serial
        alertOpen = true
      }
      if (!next.alert) alertOpen = false
    } catch (error) { console.warn("Pomodoro: invalid backend response") }
  }

  Process {
    id: backend
    command: ["python3", "-u", String(Qt.resolvedUrl("timer.py")).replace(/^file:\/\//, "")]
    stdinEnabled: true
    running: true
    stdout: SplitParser { onRead: data => root.accept(data) }
    stderr: SplitParser { onRead: data => console.warn("Pomodoro:", data) }
    onExited: { root.available = false; root.alertOpen = false }
  }

  ShellIpc {
    target: "max.pomodoro"
    function enable(): void { root.send("enable") }
    function start(): void { root.send("start") }
    function pause(): void { root.send("pause") }
    function reset(): void { root.send("reset") }
    function disable(): void { root.send("disable") }
    function dismiss(): void { root.dismiss() }
    function status(): string { return JSON.stringify({available: root.available, state: root.state}) }
  }

  OverlayWindow {
    id: alert
    shown: root.alertOpen
    WlrLayershell.namespace: "max-pomodoro"
    Rectangle {
      anchors.fill: parent
      color: Commons.Color.menu.scrim
    }
    MouseArea { anchors.fill: parent; onClicked: root.dismiss() }
    BorderSurface {
      anchors.centerIn: parent
      width: Math.min(Style.space(380), alert.width - Style.gapsOut * 2)
      height: controls.implicitHeight + Style.spacing.panelPadding * 2
      color: Commons.Color.popups.background
      radius: Style.cornerRadius
      borderSpec: Border.surfaceSpec("popups", "border", Commons.Color.popups.border, Math.max(1, Style.space(2)))
      MouseArea { anchors.fill: parent; onClicked: {} }
      TimerControls {
        id: controls
        anchors.centerIn: parent
        width: parent.width - Style.spacing.panelPadding * 2
        service: root
        announcement: true
        onCloseRequested: root.dismiss()
        focus: root.alertOpen
        Keys.onEscapePressed: root.dismiss()
      }
    }
    onShownChanged: if (shown) Qt.callLater(function() { controls.forceActiveFocus() })
  }
}
