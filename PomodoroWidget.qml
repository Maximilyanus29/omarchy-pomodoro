import QtQuick
import qs.Commons
import qs.Commons as Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "max.pomodoro"
  property var service: null
  readonly property var state: service ? service.state : ({status: "off", phase: "work", seconds: 1500})
  property bool opened: false
  readonly property string timeText: controls.formatTime(state.seconds)

  // The scoped shell facade has no reactive service registry. Retry only
  // until startup has registered our one shared service.
  function connectService() {
    if (bar && bar.shell) service = bar.shell.serviceFor("max.pomodoro")
  }
  function open() { root.opened = true }
  function close() { root.opened = false }
  onBarChanged: connectService()
  Component.onCompleted: connectService()
  Timer { interval: 500; running: !root.service; repeat: true; onTriggered: root.connectService() }

  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: !root.service || !root.service.available ? "󰔟 !"
      : root.state.status === "off" ? "󰔟"
      : (root.state.phase === "break" ? "󰅶 " : "󰔟 ")
        + (root.state.status === "running" ? "" : "󰏤 ") + root.timeText
    dimmed: root.state.status === "off"
    tooltipText: root.state.status === "off" ? strings.t("tooltipOff")
      : strings.t("tooltip").arg(strings.t(root.state.phase)).arg(strings.t(root.state.status))
    onPressed: root.opened = !root.opened
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    bar: root.bar
    owner: root
    open: root.opened
    contentWidth: panel.fittedContentWidth(Style.space(360))
    contentHeight: panel.fittedContentHeight(controls.implicitHeight)
    focusTarget: controls
    onOpenChanged: if (!open) root.close()

    TimerControls {
      id: controls
      width: parent.width
      service: root.service
      onCloseRequested: root.close()
      Keys.onEscapePressed: root.close()
    }
  }
}
