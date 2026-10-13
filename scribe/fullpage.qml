// Modo completo: a página do livro (specs/completo.md; janela.md J19–J22). Fica num arquivo
// próprio para o overlay não depender do QtWebEngine: se ele faltar, só este modo falha.
import QtQuick
import QtWebEngine

WebEngineView {
    id: view
    signal browse()                       // J20: a pessoa rolou a página à mão
    signal key(string name)               // J22: tecla da janela com o foco na página
    property bool ready: false
    url: reader.pageUrl
    Connections {                         // a página pode ficar pronta depois da view
        target: reader
        function onPageChanged() { if (view.url.toString() !== "about:blank") view.url = reader.pageUrl }
    }
    zoomFactor: reader.zoom               // C15
    backgroundColor: "#fbf8f1"
    opacity: ready ? 1 : 0                // J21: só aparece já na palavra atual
    Behavior on opacity { NumberAnimation { duration: 250 } }
    settings.javascriptCanOpenWindows: false
    settings.showScrollBars: true

    // C13: a página só recebe a palavra atual, o bloco e se há sincronia
    function push(animated) {
        if (!ready) return
        const w = reader.currentWord
        runJavaScript("scribe.set(" + (w < 0 ? "null" : w) + "," + reader.currentRow + ","
                      + reader.synced + "," + animated + ")")
    }
    function resync() { if (ready) runJavaScript("scribe.resync()") }
    // R15: altura do foco (a do arrasto da alça, J23, enquanto ele dura)
    property real focusHeight: win.focusHeight
    onFocusHeightChanged: if (ready) runJavaScript("scribe.setAnchor(" + focusHeight + ")")
    // C16: linha da página (a do arrasto da régua, J24, enquanto ele dura)
    readonly property var line: win.line
    onLineChanged: if (ready) runJavaScript("scribe.setLine(" + line[0] + "," + line[1] + ")")
    // J24: onde fica a largura da página e o tamanho da letra, em px da página
    property real boxX: 0
    property real boxW: 0
    property real em: 0
    function focusOn(row) { if (ready) runJavaScript("scribe.setFocus(" + row + ")") }

    // J11: antes de destruir a view, esvazia a página (destruir o livro inteiro trava)
    signal released()
    function release() {
        if (url.toString() === "about:blank" && !loading) released()
        else url = "about:blank"
    }
    onLoadingChanged: (req) => {
        if (req.url.toString() === "about:blank" && req.status !== WebEngineView.LoadStartedStatus)
            released()
    }

    onUrlChanged: ready = false
    onJavaScriptConsoleMessage: (level, message) => {
        if (!message.startsWith("scribe:")) return
        const m = message.slice(7)
        if (m === "ready") {                  // J21: abre já na palavra atual
            ready = true
            runJavaScript("scribe.setAnchor(" + focusHeight + ")")
            runJavaScript("scribe.setLine(" + line[0] + "," + line[1] + ")")
            push(false)
            focusOn(reader.focusRow)
        } else if (m.startsWith("metrics:")) {
            const v = m.slice(8).split(":").map(Number)
            boxX = v[0]; boxW = v[1]; em = v[2]
        } else if (m === "browse") {
            view.browse()
        } else if (m.startsWith("key:")) {
            view.key(m.slice(4))
        } else if (m.startsWith("seek:")) {   // C14
            reader.seekWordId(parseInt(m.slice(5)))
        }
    }
    // J22: nada sai da página (links externos, janelas novas)
    onNavigationRequested: (req) => {
        const u = req.url.toString()
        if (u !== "about:blank" && u !== reader.pageUrl && !u.startsWith(reader.pageUrl + "#"))
            req.reject()
    }
    onNewWindowRequested: (req) => {}

    Connections {
        target: reader
        function onCurrentChanged() { view.push(true) }
        function onImageChanged() { view.focusOn(reader.focusRow) }
    }
}
