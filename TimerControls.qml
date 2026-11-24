import QtQuick
import qs.Commons
import qs.Commons as Commons
import qs.Ui

Column {
  id: root
  required property var service
  property bool announcement: false
  signal closeRequested()
  readonly property var state: service ? service.state : ({status: "off", phase: "work", seconds: 1500})
  readonly property bool available: service && service.available
  readonly property string timeText: formatTime(state.seconds)
  spacing: Style.spacing.controlGap

  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  function formatTime(seconds) {
    var value = Math.max(0, Number(seconds) || 0)
    return I18n.formatNumber(Math.floor(value / 60)).padStart(2, I18n.formatNumber(0))
      + ":" + I18n.formatNumber(value % 60).padStart(2, I18n.formatNumber(0))
  }
  function primary() {
    if (!root.available) return
    service.send(state.status === "off" ? "enable" : state.status === "running" ? "pause" : "start")
    if (root.announcement) root.closeRequested()
  }

  Text {
    width: parent.width
    textFormat: Text.PlainText
    text: root.announcement ? strings.t(root.state.phase === "break" ? "workDone" : "breakDone") : strings.t("title")
    color: Commons.Color.foreground
    font.family: Style.font.family
    font.pixelSize: Style.font.heading
    horizontalAlignment: Text.AlignHCenter
    wrapMode: Text.Wrap
  }
  Text {
    width: parent.width
    textFormat: Text.PlainText
    text: strings.t(root.state.phase)
    color: Commons.Color.accent
    font.family: Style.font.family
    font.pixelSize: Style.font.body
    horizontalAlignment: Text.AlignHCenter
  }
  Text {
    objectName: "countdown"
    width: parent.width
    textFormat: Text.PlainText
    text: root.timeText
    color: Commons.Color.foreground
    font.family: Style.font.family
    font.pixelSize: Style.space(56)
    horizontalAlignment: Text.AlignHCenter
  }
  Text {
    width: parent.width
    textFormat: Text.PlainText
    text: strings.t(root.state.status)
    color: Commons.Color.foreground
    opacity: 0.65
    font.family: Style.font.family
    font.pixelSize: Style.font.bodySmall
    horizontalAlignment: Text.AlignHCenter
    wrapMode: Text.Wrap
  }
  Row {
    spacing: Style.spacing.controlGap
    anchors.horizontalCenter: parent.horizontalCenter
    Button {
      objectName: "primaryAction"
      text: strings.t(root.state.status === "off" ? "enable" : root.state.status === "running" ? "pause" : root.state.status === "paused" ? "resume" : "start")
      selected: true
      focusable: true
      enabled: root.available
      opacity: enabled ? 1 : 0.45
      onClicked: root.primary()
    }
    Button {
      objectName: "resetAction"
      text: strings.t("reset")
      visible: root.state.status !== "off" && !root.announcement
      focusable: true
      enabled: root.available
      onClicked: root.service.send("reset")
    }
  }
  Row {
    spacing: Style.spacing.controlGap
    anchors.horizontalCenter: parent.horizontalCenter
    Button {
      text: strings.t("disable")
      visible: root.state.status !== "off" && !root.announcement
      focusable: true
      enabled: root.available
      onClicked: root.service.send("disable")
    }
    Button {
      text: strings.t("close")
      focusable: true
      onClicked: root.closeRequested()
    }
  }
  Text {
    width: parent.width
    visible: !root.available || root.state.error === "config"
    textFormat: Text.PlainText
    text: strings.t(!root.available ? "backendError" : "configError")
    color: Commons.Color.urgent
    wrapMode: Text.Wrap
    font.family: Style.font.family
    font.pixelSize: Style.font.bodySmall
    horizontalAlignment: Text.AlignHCenter
  }
  Button {
    text: strings.t("retry")
    visible: !root.available
    anchors.horizontalCenter: parent.horizontalCenter
    focusable: true
    onClicked: if (root.service) root.service.retry()
  }
  Text {
    width: parent.width
    visible: !root.announcement
    textFormat: Text.PlainText
    text: strings.t("configHint")
    color: Commons.Color.foreground
    opacity: 0.5
    wrapMode: Text.WrapAnywhere
    horizontalAlignment: Text.AlignHCenter
    font.family: Style.font.family
    font.pixelSize: Style.font.bodySmall
  }
}
