// Janela do scribe — specs/janela.md (J1–J10)
import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import QtQuick.Dialogs
import QtQuick.Controls.Basic
import QtQuick.Window

Window {
    id: win

    readonly property color ink: "#15131f"
    readonly property color paper: "#f3eee4"
    readonly property color ribbon: "#d9b25f"
    readonly property int pad: 28
    readonly property string face: "Roboto"

    // G: espaço reservado à direita para a imagem (painel + espaçamento)
    readonly property real imageReserve: reader.imagePanelWidth > 0 ? reader.imagePanelWidth + reader.imageGap : 0
    readonly property int dock: 48         // J5: faixa da barra (34) + progresso (10) + folga
    // J19: modo completo, a página do livro no lugar do overlay
    readonly property bool full: reader.fullMode
    property bool browsing: false          // J4: texto solto da narração (roda do mouse)
    // R15/J23: altura do foco; enquanto a alça é arrastada vale o valor do arrasto, que só
    // é salvo ao soltar
    property real dragFocus: -1
    readonly property real focusHeight: dragFocus >= 0 ? dragFocus : reader.focusHeight
    // C16: [comprimento, posição] da linha da página; a do arrasto da régua enquanto ele dura (J24)
    property var dragLine: null
    readonly property var line: dragLine ? dragLine : [reader.lineMeasure, reader.lineOffset]
    onFocusHeightChanged: list.requestFollow(false)
    function resync() {                    // J4: volta o texto para a palavra narrada
        browsing = false
        list.requestFollow(true)
        if (page.item) page.item.resync()  // J20
    }
    // HoverHandler no painel: recebe a passagem do mouse mesmo com o cursor sobre o texto
    // (a MouseArea de fundo perdia o hover para os parágrafos, e a barra não aparecia)
    property bool hovering: panelHover.hovered || barHover.hovered || popHover.hovered
    // J5/J14: a barra some com um pequeno atraso, para o mouse atravessar o vão até a
    // janela da barra no modo de uma linha (e de volta) sem ela sumir no caminho
    readonly property bool barWanted: (hovering || bgMenu.opened) && !reader.passClicks
    property bool barShown: false
    onBarWantedChanged: if (barWanted) { barHide.stop(); barShown = true } else barHide.restart()
    Timer { id: barHide; interval: 350; onTriggered: win.barShown = false }

    width: 760; height: 300
    minimumWidth: 320; minimumHeight: full ? 240 : reader.onelineHeight
    // O2/J14: o modo de uma linha é consequência da altura da janela (J19: menos no completo)
    readonly property bool oneline: !full && height < reader.onelineThreshold
    // G7: janela mais alta que larga põe as imagens no texto (a ponte usa a largura de antes
    // do painel). Depende do modo atual (folga), por isso não é uma ligação; e é adiada
    // para painel e largura já terem se acertado juntos.
    property bool vertical: false
    function updateVertical() {
        vertical = !full && reader.isVertical(width, height,
                                              height < reader.onelineThreshold, vertical)
    }
    onVerticalChanged: Qt.callLater(syncImage)
    readonly property real lineH: reader.linePitch          // O1: medida na tela
    visible: true
    color: "transparent"
    title: reader.bookTitle
    // J1/R10: solta = janela comum; fixa = por cima das outras; J3: cliques atravessam
    // (o atravessar cliques usa a forma de entrada do X11, para o botão "soltar" seguir clicável)
    flags: Qt.Window | Qt.FramelessWindowHint
           | (reader.onTop ? Qt.WindowStaysOnTopHint : 0)

    function applyGeometry(g) {
        if (g.length === 4) {
            if (g[0] >= 0) { x = g[0]; y = g[1]; width = g[2] }
            height = g[3]
        }
    }
    // C12: geometria padrão do modo completo, na tela da janela
    function screenRect() {
        return [screen.virtualX, screen.virtualY, screen.width, screen.height]
    }
    // C17/J25: maximizada só no modo completo; o estado é o da janela (o sistema também
    // maximiza), e a preferência o acompanha
    readonly property bool maxed: visibility === Window.Maximized
    property var pendingGeo: null                 // geometria do overlay, depois de restaurar
    property bool wasMaxed: false
    property bool started: false
    property var maxGeo: []
    Timer {
        id: restoreCheck; interval: 200
        onTriggered: {
            const g = win.maxGeo
            if (win.full && !win.maxed && g.length === 4 && win.x === g[0] && win.y === g[1]
                    && win.width === g[2] && win.height === g[3]) {
                const r = win.screenRect()
                win.applyGeometry(reader.fullGeometry(r[0], r[1], r[2], r[3]))
            }
        }
    }
    onVisibilityChanged: {
        if (visibility !== Window.Maximized && visibility !== Window.Windowed) return
        // a janela aparece "normal" antes de abrir: isso não é a pessoa restaurando (C17)
        if (!started) return
        const on = visibility === Window.Maximized   // aqui o maxed ainda é o de antes
        if (full) {
            reader.setMaximized(on)
            // restaurar devolve a geometria salva (a de antes de maximizar): o sistema nem
            // sempre a conhece, quando a janela maximiza logo ao aparecer ou ao trocar de modo.
            // Só se ele não restaurou: arrastar a janela maximizada a restaura sob o mouse.
            if (on) maxGeo = [x, y, width, height]
            else if (wasMaxed) restoreCheck.restart()
        } else if (pendingGeo && !on) { applyGeometry(pendingGeo); pendingGeo = null }
        wasMaxed = on
    }
    function toggleMaximized() { if (maxed) showNormal(); else showMaximized() }
    function toggleFull() {                       // J19, C11, C12
        saveGeo.stop()
        reader.saveGeometry(x, y, width, height)  // a do modo que sai (C17: não a de maximizada)
        if (!full) syncImageOff()
        else if (page.item) { page.holding = true; page.item.release() }
        const r = screenRect()
        const g = reader.toggleFull(r[0], r[1], r[2], r[3])
        if (!full && maxed) { pendingGeo = g; showNormal() }    // C17: o overlay nunca maximizado
        else applyGeometry(g)
        if (full && reader.fullMaximized) showMaximized()
        browsing = false
        Qt.callLater(updateVertical)
        Qt.callLater(syncImage)
        Qt.callLater(() => list.requestFollow(false))
    }
    property bool closingDown: false
    // J11: fechar pelo gerenciador de janelas passa pelo mesmo caminho do botão
    // (o quit do Qt fecha as janelas de novo: aí já pode)
    onClosing: (close) => { close.accepted = closingDown; if (!closingDown) reader.quit() }
    Component.onCompleted: {
        const r = screenRect()
        applyGeometry(full ? reader.fullGeometry(r[0], r[1], r[2], r[3]) : reader.geometry)
        started = true
        if (full && reader.fullMaximized) showMaximized()                // C17
        lastLine = reader.linePitch
        updateVertical()
        if (reader.passClicks) {                 // abriu já atravessando: aplica e avisa
            Qt.callLater(updateInputRegion)
        }
        Qt.callLater(syncImage)                  // abriu dentro da janela de uma imagem (R5)
    }
    onXChanged: saveGeo.restart()
    onYChanged: saveGeo.restart()
    onWidthChanged: { saveGeo.restart(); if (reader.passClicks) Qt.callLater(updateInputRegion); Qt.callLater(updateVertical) }
    onHeightChanged: { saveGeo.restart(); Qt.callLater(updateVertical) }
    Timer { id: saveGeo; interval: 600; onTriggered: reader.saveGeometry(win.x, win.y, win.width, win.height) }

    Connections {
        target: reader
        function onVisibilityToggleRequested() { win.visible = !win.visible }
        function onJumped() { win.resync() }          // J4: pulo no áudio ressincroniza
        function onClosing() {                        // J11: esvazia a página antes de sair
            win.closingDown = true
            win.visible = false
            if (page.item) page.item.release()
            else reader.finishQuit()
        }
    }

    // J3: atravessar cliques, menos no botão "soltar"
    function updateInputRegion() {
        if (reader.passClicks) {
            const p = releaseBtn.mapToItem(null, 0, 0)
            reader.setInputRegion(p.x, p.y, releaseBtn.width, releaseBtn.height)
        } else {
            reader.clearInputRegion()
        }
    }
    property real lastLine: 0
    Connections {
        target: reader
        function onLineChanged() {                    // O4
            if (win.lastLine > 0)
                win.height = reader.heightAfterLineChange(win.height, win.lastLine, reader.linePitch)
            win.lastLine = reader.linePitch
            list.requestFollow(false)
        }
    }
    // trocar de modo com a imagem à mostra abre ou devolve o espaço dela (J14, G)
    onOnelineChanged: syncImage()
    // O1: sonda invisível que mede a altura real de uma linha do texto exibido
    Text {
        id: lineProbe
        visible: false
        textFormat: Text.RichText
        font.family: win.face
        font.pixelSize: reader.fontSize
        text: '<div style="line-height:128%">Ag<br>Ag<br>Ag<br>Ag</div>'
        function report() { if (lineProbe.contentHeight > 0) reader.setLinePitch(lineProbe.contentHeight / 4) }
        onContentHeightChanged: report()
        Component.onCompleted: report()
    }
    Connections {
        target: reader
        function onPrefsChanged() {
            Qt.callLater(win.updateInputRegion)
        }
    }

    // J17: balão da imagem à mostra, fora da faixa
    property bool imgPinned: false
    property string lastThumb: ""
    Connections {
        target: reader
        function onImageChanged() {
            if (reader.image !== win.lastThumb) {
                win.imgPinned = false
                if (reader.image !== "" && win.oneline) pulse.restart()
                win.lastThumb = reader.image
            }
        }
    }
    Window {
        id: imgPop
        flags: Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        color: "transparent"
        visible: thumb.visible && (thumbHover.hovered || win.imgPinned) && popImg.status === Image.Ready
        readonly property real maxW: 460
        readonly property real maxH: 340
        readonly property real ratio: popImg.implicitHeight > 0 ? popImg.implicitWidth / popImg.implicitHeight : 1.4
        width: Math.round(Math.min(maxW, maxH * ratio)) + 16
        height: Math.round(Math.min(maxH, maxW / ratio)) + 16
        // acima se couber, senão abaixo; nunca no lugar da barra (J14): fica do outro lado
        // dela ou, se a tela obrigar os dois ao mesmo lado, depois dela
        x: Math.max(win.screen.virtualX, Math.min(win.screen.virtualX + win.screen.width - width,
                                                  win.x + thumb.x + thumb.width - width))
        y: {
            const upEdge = barPop.below ? win.y : barPop.y
            const downEdge = barPop.below ? barPop.y + barPop.height : win.y + win.height
            const above = upEdge - height - 8
            return above >= win.screen.virtualY ? above : downEdge + 8
        }
        Rectangle {
            anchors.fill: parent
            radius: 10
            color: win.ink
            border.width: 1; border.color: Qt.rgba(0.85, 0.70, 0.37, 0.5)
            Image {
                id: popImg
                anchors.fill: parent; anchors.margins: 8
                source: reader.image
                fillMode: Image.PreserveAspectFit
                smooth: true; mipmap: true
            }
        }
    }

    // J14: no modo de uma linha a barra mora numa janelinha própria, encostada à direita,
    // logo abaixo da faixa (ou acima, se não couber na tela): nunca cobre o texto
    Window {
        id: barPop
        flags: Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        color: "transparent"
        readonly property int gap: 6
        width: bar.width + 14
        height: 34
        readonly property bool below: win.y + win.height + gap + height
                                      <= win.screen.virtualY + win.screen.height
        x: Math.max(win.screen.virtualX, Math.min(win.screen.virtualX + win.screen.width - width,
                                                  win.x + win.width - width))
        y: below ? win.y + win.height + gap : win.y - gap - height
        visible: win.oneline && win.visible && bar.visible
        Item { anchors.fill: parent; HoverHandler { id: popHover } }
    }

    // J5: balãozinho com o nome do botão, numa janela própria (a da barra no modo de uma
    // linha é baixa demais e o cortaria)
    property Item tipFor: null
    property bool tipShown: false
    function hoverTip(item, on) {
        if (on) { tipFor = item; tipShown = false; tipDelay.restart() }
        else if (tipFor === item) { tipDelay.stop(); tipShown = false; tipFor = null }
    }
    Timer {
        id: tipDelay; interval: 500
        onTriggered: { if (win.tipFor) { tipPop.place(); win.tipShown = true } }
    }
    Window {
        id: tipPop
        flags: Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
               | Qt.WindowTransparentForInput
        color: "transparent"
        width: tipText.implicitWidth + 16; height: tipText.implicitHeight + 10
        visible: win.tipShown && win.tipFor !== null && win.tipFor.visible && win.tipFor.tip !== ""
                 && win.visible
        function place() {
            const b = win.tipFor
            const top = b.mapToGlobal(b.width / 2, 0)
            const bottom = b.mapToGlobal(b.width / 2, b.height)
            const sx = win.screen.virtualX, sy = win.screen.virtualY
            x = Math.max(sx, Math.min(sx + win.screen.width - width, Math.round(top.x - width / 2)))
            // acima do botão; no modo de uma linha com a barra embaixo, abaixo (longe da faixa).
            // Se o lado preferido sair da tela, vai para o outro; e nunca sai da tela
            const above = top.y - height - 6, below = bottom.y + 6
            const fitsAbove = above >= sy
            const fitsBelow = below + height <= sy + win.screen.height
            const preferUp = !(win.oneline && barPop.below)
            const up = preferUp ? (fitsAbove || !fitsBelow) : (!fitsBelow && fitsAbove)
            y = Math.max(sy, Math.min(sy + win.screen.height - height, Math.round(up ? above : below)))
        }
        Rectangle {
            anchors.fill: parent
            radius: 6
            color: win.ink
            border.width: 1; border.color: Qt.rgba(0.85, 0.70, 0.37, 0.4)
            Text {
                id: tipText
                anchors.centerIn: parent
                text: win.tipFor ? win.tipFor.tip : ""
                color: win.paper
                font.family: win.face; font.pixelSize: 12
            }
        }
    }

    // G: a janela cresce para a direita para a imagem e depois volta
    property string shownImage: ""          // imagem com espaço aberto ao lado do texto
    function syncImage() {
        // pela altura, e não por `oneline`: na abertura a ligação ainda não se atualizou
        const many = win.height >= reader.onelineThreshold
        const side = many && !win.vertical && !win.full                     // G7, J19
        const want = reader.image !== "" && side ? reader.image : ""
        if (want === win.shownImage) return
        win.shownImage = want
        if (want !== "") {
            win.width = reader.layoutImage(win.x, win.width, win.height - win.dock,
                                           win.screen.virtualX + win.screen.width)
        } else {
            const w = reader.restoreWidth()
            if (w > 0) win.width = w
        }
    }
    // J19: ao entrar no modo completo, a janela devolve o espaço da imagem antes de trocar
    function syncImageOff() {
        if (shownImage === "") return
        shownImage = ""
        const w = reader.restoreWidth()
        if (w > 0) win.width = w
    }
    Connections {
        target: reader
        function onImageChanged() { win.syncImage() }
    }

    // ------------------------------------------------------------ painel
    Rectangle {
        id: panel
        anchors.fill: parent
        radius: win.full ? 0 : 14
        readonly property color bgC: reader.bgColor
        // J19: no modo completo a janela é opaca, com a faixa da barra escura
        color: win.full ? win.ink
             : reader.bgImage !== "" ? "transparent" : Qt.rgba(bgC.r, bgC.g, bgC.b, reader.bgOpacity)

        // R12/J15: imagem de fundo, cobrindo o painel e cortada nas bordas arredondadas
        Item {
            id: bgMask
            anchors.fill: parent
            visible: false
            layer.enabled: true
            Rectangle { anchors.fill: parent; radius: panel.radius; color: "white" }
        }
        Image {
            anchors.fill: parent
            visible: reader.bgImage !== "" && !win.full
            source: reader.bgImage
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            opacity: reader.bgOpacity
            layer.enabled: true
            layer.effect: MultiEffect {
                maskEnabled: true
                maskSource: bgMask
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1.0
            }
        }
        border.width: win.hovering && !reader.locked ? 1 : 0
        border.color: Qt.rgba(0.95, 0.93, 0.89, 0.12)

        HoverHandler { id: panelHover }

        // J2: arrastar pelo fundo
        MouseArea {
            id: hoverArea
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton
            onPressed: if (!reader.locked) win.startSystemMove()
            onWheel: (w) => {
                win.browsing = true
                list.contentY = Math.max(list.originY - list.height,
                    Math.min(list.contentY - w.angleDelta.y, list.contentHeight + list.originY))
            }
            onDoubleClicked: reader.togglePlay()
        }

        // ------------------------------------------------------------ texto (J4)
        // ------------------------------------------------------------ página (J19–J22)
        Loader {
            id: page
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: parent.height - win.dock - bar.height + 34
            // ao voltar para o overlay a view fica até esvaziar a página (J11)
            property bool holding: false
            active: win.full || holding
            visible: win.full
            source: "fullpage.qml"
            onLoaded: {
                item.browse.connect(() => { win.browsing = true })
                item.key.connect(win.windowKey)
                item.released.connect(() => {
                    if (win.closingDown) reader.finishQuit()
                    else if (!win.full) page.holding = false
                })
            }
        }
        Text {
            anchors.centerIn: page
            visible: win.full && (page.status !== Loader.Ready || !page.item.ready)
            text: page.status === Loader.Error ? "o modo completo precisa do QtWebEngine"
                                               : "preparando o livro…"
            color: win.paper; opacity: 0.6
            font.family: win.face; font.pixelSize: 15; font.italic: true
        }

        ListView {
            id: list
            objectName: "lst"
            visible: !win.full
            anchors.fill: parent
            // J14: no modo de uma linha a lista tem a altura de uma linha, centralizada
            anchors.topMargin: win.oneline ? reader.stripMargins(win.height)[0] : 0
            anchors.bottomMargin: win.oneline ? reader.stripMargins(win.height)[1] : 0
            layer.enabled: !win.oneline
            layer.effect: MultiEffect {
                maskEnabled: true
                maskSource: fadeMask
                maskThresholdMin: 0.0
                maskSpreadAtMin: 1.0
            }
            anchors.leftMargin: win.pad - 8   // espaço para a fita dentro do recorte
            anchors.rightMargin: win.pad + (win.imageReserve > 0 ? win.imageReserve : 0)
                                 + (win.oneline ? thumb.width + 10 : 0)  // J17: lugar fixo, a linha não muda
            clip: true
            interactive: false
            model: blocks
            spacing: 0
            header: Item { height: win.oneline ? 0 : list.height * win.focusHeight }   // R15
            footer: Item { height: win.oneline ? list.height : list.height * (1 - win.focusHeight) }

            // A rolagem é animada à mão, quadro a quadro: se um parágrafo acima muda de altura
            // no meio do caminho (karaokê, peso da fonte, delegate recriado), o deslocamento é
            // compensado na hora e a animação segue sem solavanco.
            QtObject {
                id: scrollAnim
                property bool running: false
                property real from: 0
                property real to: 0
                property real elapsed: 0
                property real duration: 450
                property bool slow: false          // G10/J18: palavra ↔ imagem, mais lenta
                property bool focusMove: false
                function start() { elapsed = 0; running = true }
                function stop() { running = false; focusMove = false }
            }
            FrameAnimation {
                running: scrollAnim.running
                onTriggered: list.step(frameTime)
            }
            function step(dt) {
                compensate()
                if (win.browsing) { scrollAnim.stop(); return }
                scrollAnim.elapsed += dt * 1000
                const p = Math.min(1, scrollAnim.elapsed / scrollAnim.duration)
                const e = scrollAnim.slow ? (1 - Math.cos(Math.PI * p)) / 2   // entra e sai devagar
                                          : 1 - Math.pow(1 - p, 3)
                contentY = scrollAnim.from + (scrollAnim.to - scrollAnim.from) * e
                if (p >= 1) scrollAnim.stop()
            }
            // o item seguido fica parado na tela quando o que está acima dele muda de altura
            property int refRow: -1
            property real refY: 0
            function remember(r) {
                const it = itemAtIndex(r)
                refRow = it ? r : -1
                refY = it ? it.y : 0
            }
            function compensate() {
                if (refRow < 0) return
                const it = itemAtIndex(refRow)
                if (!it) { refRow = -1; return }
                const d = it.y - refY
                refY = it.y
                if (Math.abs(d) < 0.5 || win.browsing) return
                contentY += d
                if (scrollAnim.running) { scrollAnim.from += d; scrollAnim.to += d }
            }

            // J4: mantém a linha da palavra atual na altura do foco (R15)
            // Nunca reposiciona a lista de dentro de um tratador de delegate: isso pode destruir
            // o delegate no meio do próprio código (segfault em pulos rápidos). Toda chamada é
            // adiada para o laço de eventos e várias no mesmo ciclo viram uma só.
            property bool followAnimated: false
            // G10: no modo vertical, a imagem em foco fica centralizada no lugar da palavra
            readonly property int focusRow: win.vertical ? reader.focusRow : -1
            onFocusRowChanged: { scrollAnim.focusMove = true; requestFollow(true) }
            function requestFollow(animated) {
                followAnimated = animated
                Qt.callLater(list.follow)
            }
            function follow() {
                let animated = followAnimated
                const img = focusRow >= 0
                const r = img ? focusRow : reader.currentRow
                if (win.browsing || r < 0) return
                compensate()
                let item = itemAtIndex(r)
                if (!item) {
                    positionViewAtIndex(r, ListView.Beginning)
                    item = itemAtIndex(r)
                    animated = false
                    if (!item) return
                }
                const anchorY = win.oneline ? 0 : height * win.focusHeight
                const target = img ? item.y + (item.height - height) / 2
                                   : item.y + item.lineY - anchorY
                remember(r)
                if (Math.abs(target - contentY) < 1) return
                if (animated && scrollAnim.running && Math.abs(scrollAnim.to - target) < 1) return
                if (animated) {
                    const slow = scrollAnim.focusMove
                    scrollAnim.stop()
                    scrollAnim.focusMove = slow
                    scrollAnim.slow = slow
                    scrollAnim.duration = slow ? 1100 : 450
                    scrollAnim.from = contentY
                    scrollAnim.to = target
                    scrollAnim.start()
                } else {
                    scrollAnim.stop()
                    contentY = target
                }
            }
            onHeightChanged: requestFollow(false)
            // a lista estima a altura dos parágrafos ainda não criados; quando um parágrafo
            // acima é criado de verdade, tudo se desloca e o enquadramento precisa ser refeito
            onOriginYChanged: { Qt.callLater(compensate); requestFollow(scrollAnim.running) }
            onContentHeightChanged: { Qt.callLater(compensate); requestFollow(scrollAnim.running) }
            Component.onCompleted: requestFollow(false)

            delegate: Item {
                id: row
                required property int index
                required property string kind
                required property string html
                required property bool shown
                required property string src
                readonly property bool current: index === reader.currentRow
                // espaçamento no próprio HTML: texto visível e medidor têm o mesmo layout
                readonly property string rich: '<div style="line-height:128%">' + html + '</div>'
                // y da linha da palavra atual dentro do parágrafo
                readonly property real lineY: current && meter.item ? meter.item.y + meter.item.lineY : 0
                onLineYChanged: if (current) list.requestFollow(true)
                onCurrentChanged: if (current) list.requestFollow(true)
                width: list.width
                // G8: imagens só entram na lista no modo vertical
                readonly property bool inline: kind === "img"
                visible: shown && (!inline || win.vertical)
                height: !visible ? 0 : inline ? fig.height + gap * 2 : body.implicitHeight + gap
                readonly property real gap: kind === "h" ? reader.fontSize * 0.9 : reader.fontSize * 0.7

                // J18: a imagem no texto, esmaecida fora da janela de tempo dela (R5)
                Loader {
                    id: fig
                    active: row.inline && row.visible
                    x: 18 + (row.width - 18 - width) / 2
                    y: row.gap                        // tamanho vem do item (G9)
                    sourceComponent: Item {
                        readonly property var size: reader.inlineSize(row.width - 18, win.height,
                                                                      pic.implicitWidth, pic.implicitHeight)
                        width: size[0]; height: size[1]
                        opacity: row.src === reader.image ? 1 : 0.4
                        Behavior on opacity { NumberAnimation { duration: 500 } }
                        Image {
                            id: pic
                            source: row.src
                            anchors.fill: parent
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                            smooth: true; mipmap: true
                            visible: false
                        }
                        MultiEffect {
                            source: pic
                            anchors.fill: parent
                            maskEnabled: true
                            maskSource: figMask
                        }
                        Item {
                            id: figMask
                            anchors.fill: parent
                            layer.enabled: true
                            visible: false
                            Rectangle { anchors.fill: parent; radius: 8 }
                        }
                    }
                }

                Text {
                    id: body
                    visible: !row.inline
                    x: 18
                    y: row.kind === "h" ? row.gap * 0.6 : 0
                    width: parent.width - x                    // J13: sem limite de linha
                    text: row.rich
                    textFormat: Text.RichText
                    wrapMode: Text.WordWrap
                    color: win.paper
                    linkColor: win.paper
                    font.family: win.face
                    // J14: no modo de uma linha tudo tem o mesmo tamanho, para caber na faixa
                    font.pixelSize: win.oneline ? reader.fontSize
                                  : row.kind === "h" ? reader.fontSize * 1.12
                                  : row.kind === "note" ? reader.fontSize * 0.78
                                  : reader.fontSize
                    font.weight: row.current || row.kind === "h" ? Font.Medium : Font.Normal
                    font.capitalization: row.kind === "h" ? Font.Capitalize : Font.MixedCase
                    style: reader.bgOpacity < 0.35 ? Text.Raised : Text.Normal
                    styleColor: Qt.rgba(0, 0, 0, 0.55)
                    onLinkActivated: (link) => reader.seekLink(link)   // R1
                    HoverHandler { cursorShape: body.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor }
                }

                // a fita: marcador dourado ao lado do parágrafo atual
                Rectangle {
                    visible: row.current
                    x: 0; y: body.y + 4
                    width: 3; height: Math.max(0, body.implicitHeight - 8)
                    radius: 1.5
                    color: win.ribbon
                    opacity: reader.synced ? 1 : 0.35
                    Behavior on opacity { NumberAnimation { duration: 300 } }
                }

                // medidor invisível: mesmo texto e fonte, só para achar a linha da palavra
                Loader {
                    id: meter
                    active: row.current
                    sourceComponent: TextEdit {
                        // depende do texto e do layout, não só do offset
                        readonly property real lineY: (text, width, contentHeight,
                            reader.currentCharOffset < length ? positionToRectangle(reader.currentCharOffset).y : 0)
                        x: body.x; y: body.y
                        width: body.width
                        text: row.rich
                        textFormat: TextEdit.RichText
                        wrapMode: TextEdit.WordWrap
                        font: body.font
                        readOnly: true
                        enabled: false
                        opacity: 0
                    }
                }
            }
        }

        // esmaece o texto nas bordas de cima e de baixo, sem pintar nada por cima do fundo
        Item {
            id: fadeMask
            anchors.fill: list
            visible: false
            layer.enabled: true
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.16; color: "white" }
                    GradientStop { position: 0.80; color: "white" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // ------------------------------------------------------------ aviso (J10)
        Text {
            anchors { left: parent.left; verticalCenter: bar.verticalCenter; leftMargin: win.pad + 10 }
            text: reader.status
            visible: text !== "" && bar.opacity < 0.5 && !win.oneline
            z: 2
            color: win.paper
            opacity: 0.55
            font.family: win.face
            font.pixelSize: 12
            font.italic: true
        }

        // ------------------------------------------------------------ faixa da barra (J5)
        // o texto aparece por baixo, mas cliques aqui nunca chegam às palavras
        MouseArea {
            id: dockArea
            enabled: !win.oneline
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: win.dock + bar.height - 34
            z: 1
            hoverEnabled: true
            onPressed: if (!reader.locked) win.startSystemMove()
        }

        // ------------------------------------------------------------ barra (J5)
        Item {
            id: bar
            z: 2
            anchors { left: parent.left; right: parent.right; bottom: progress.top }
            anchors.leftMargin: win.pad
            anchors.rightMargin: win.pad - 6
            height: compact ? 62 : 34
            opacity: win.barShown || (win.full && !reader.passClicks) ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 180 } }
            HoverHandler { id: barHover }
            states: State {
                // J14: a barra vai para a janela própria (barPop), fora da faixa
                name: "oneline"; when: win.oneline
                AnchorChanges {
                    target: bar
                    anchors.left: undefined; anchors.right: undefined; anchors.bottom: undefined
                }
                ParentChange { target: bar; parent: barPop.contentItem; x: 10; y: 0 }
                PropertyChanges { target: bar; width: look.implicitWidth + play.implicitWidth + 10 }
            }

            // fundo próprio: os controles continuam legíveis com o painel transparente
            Rectangle {
                anchors.fill: parent
                anchors.leftMargin: -10; anchors.rightMargin: -4
                radius: 8
                // no modo de uma linha a barra fica solta fora da janela: fundo opaco
                color: Qt.rgba(0.082, 0.075, 0.122, win.oneline ? 1 : Math.max(0.8, reader.bgOpacity))
            }

            Text {
                anchors.verticalCenter: look.verticalCenter
                anchors.left: parent.left
                anchors.right: look.left
                anchors.rightMargin: 12
                elide: Text.ElideRight
                visible: !win.oneline
                text: reader.chapterTitle
                color: win.paper; opacity: 0.6
                font.family: win.face; font.pixelSize: 12
            }

            // J5: aparência (look) e reprodução (play); sem espaço para as duas numa linha,
            // a barra cresce para cima e a aparência vai para uma fileira própria
            readonly property bool compact: !win.oneline
                && width < look.implicitWidth + play.implicitWidth + 2 + 80
            Row {
                id: look
                anchors.right: bar.compact ? parent.right : play.left
                anchors.rightMargin: bar.compact ? 0 : 2
                y: bar.compact ? 4 : (parent.height - height) / 2
                spacing: 2

                // J5: botão com ícone desenhado (filhos, numa área de 18×18) ou texto curto,
                // e o nome num balãozinho (tip)
                component Btn: Item {
                    id: btn
                    signal clicked()
                    signal rightClicked()
                    property bool active: false
                    property string tip: ""
                    property alias text: label.text
                    property alias size: label.font.pixelSize
                    readonly property color ink: active ? win.ribbon : win.paper
                    default property alias glyph: glyphArea.data
                    width: label.text !== "" ? Math.max(28, label.implicitWidth + 12) : 28
                    height: 26
                    opacity: ma.containsMouse ? 1 : 0.7
                    Text {
                        id: label
                        anchors.fill: parent
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        color: btn.ink
                        font.family: win.face; font.pixelSize: 13
                    }
                    Item { id: glyphArea; anchors.centerIn: parent; width: 18; height: 18 }
                    MouseArea {
                        id: ma; anchors.fill: parent; hoverEnabled: true
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        cursorShape: Qt.PointingHandCursor
                        onClicked: (e) => e.button === Qt.RightButton ? btn.rightClicked() : btn.clicked()
                        onContainsMouseChanged: win.hoverTip(btn, containsMouse)
                    }
                }

                // J4: aparece só com o texto solto da narração; mira de "recentralizar"
                Item {
                    id: resyncBtn
                    objectName: "resyncBtn"
                    visible: win.browsing
                    width: 28; height: 26
                    Rectangle {
                        anchors.centerIn: parent
                        width: 24; height: 24; radius: 12
                        color: Qt.rgba(0.85, 0.70, 0.37, resyncMa.containsMouse ? 0.18 : 0)
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                    Shape {
                        anchors.centerIn: parent
                        width: 18; height: 18
                        preferredRendererType: Shape.CurveRenderer
                        ShapePath {   // anel
                            strokeColor: win.ribbon; strokeWidth: 1.5; fillColor: "transparent"
                            startX: 14; startY: 9
                            PathArc { x: 4; y: 9; radiusX: 5; radiusY: 5 }
                            PathArc { x: 14; y: 9; radiusX: 5; radiusY: 5 }
                        }
                        ShapePath {   // ponto central
                            strokeColor: "transparent"; fillColor: win.ribbon
                            startX: 10.8; startY: 9
                            PathArc { x: 7.2; y: 9; radiusX: 1.8; radiusY: 1.8 }
                            PathArc { x: 10.8; y: 9; radiusX: 1.8; radiusY: 1.8 }
                        }
                        ShapePath {   // quatro marcas
                            strokeColor: win.ribbon; strokeWidth: 1.5; fillColor: "transparent"
                            capStyle: ShapePath.RoundCap
                            startX: 9; startY: 0.8;  PathLine { x: 9; y: 3.2 }
                            PathMove { x: 9; y: 14.8 }  PathLine { x: 9; y: 17.2 }
                            PathMove { x: 0.8; y: 9 }   PathLine { x: 3.2; y: 9 }
                            PathMove { x: 14.8; y: 9 }  PathLine { x: 17.2; y: 9 }
                        }
                    }
                    MouseArea {
                        id: resyncMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: win.resync()
                    }
                }
                Item { width: 6; height: 1; visible: win.browsing }

                // J19: livro aberto; ativo no modo completo
                Btn { id: fullBtn; active: win.full
                      tip: win.full ? "Voltar ao overlay" : "Modo completo (o livro como num leitor)"
                      onClicked: win.toggleFull()
                      Shape {
                          anchors.fill: parent
                          preferredRendererType: Shape.CurveRenderer
                          ShapePath {   // duas páginas abertas
                              strokeColor: fullBtn.ink; strokeWidth: 1.4
                              fillColor: win.full ? Qt.rgba(0.85, 0.70, 0.37, 0.25) : "transparent"
                              joinStyle: ShapePath.RoundJoin
                              startX: 9; startY: 4.5
                              PathQuad { x: 1.5; y: 3.5; controlX: 5; controlY: 2.5 }
                              PathLine { x: 1.5; y: 14.5 }
                              PathQuad { x: 9; y: 15.5; controlX: 5; controlY: 13.5 }
                              PathQuad { x: 16.5; y: 14.5; controlX: 13; controlY: 13.5 }
                              PathLine { x: 16.5; y: 3.5 }
                              PathQuad { x: 9; y: 4.5; controlX: 13; controlY: 2.5 }
                              PathLine { x: 9; y: 15.5 }
                          }
                      } }
                Item { width: 6; height: 1 }
                Btn { text: "A"; size: 11; tip: win.full ? "Diminuir o zoom: " + Math.round(reader.zoom * 100) + "%"
                                                        : "Diminuir a letra"
                      onClicked: reader.adjustFont(-2) }
                Btn { text: "A"; size: 17; tip: win.full ? "Aumentar o zoom: " + Math.round(reader.zoom * 100) + "%"
                                                        : "Aumentar a letra"
                      onClicked: reader.adjustFont(2) }
                // R8: cor do texto (abre o seletor) e opacidade do texto (J19: não no completo)
                Item {
                    visible: !win.full
                    width: 26; height: 26
                    Rectangle {
                        anchors.centerIn: parent
                        width: 14; height: 14; radius: 7
                        color: reader.textColor
                        border.width: 1
                        border.color: Qt.rgba(1, 1, 1, colorMa.containsMouse ? 0.8 : 0.35)
                    }
                    MouseArea {
                        id: colorMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: win.openTextColor()
                    }
                }
                Btn { visible: !win.full
                      tip: "Opacidade do texto: " + Math.round(reader.textOpacity * 100) + "%"
                      onClicked: reader.setTextOpacity(reader.textOpacity <= 0.41 ? 1.0 : reader.textOpacity - 0.15)
                      // um "A" com a transparência atual do texto, sobre um xadrezinho
                      Grid {
                          anchors.centerIn: parent; columns: 3
                          Repeater { model: 9; Rectangle { width: 5; height: 5
                                     color: Qt.rgba(1, 1, 1, index % 2 ? 0.05 : 0.22) } }
                      }
                      Text { anchors.centerIn: parent; text: "A"; font.family: win.face
                             font.pixelSize: 15; font.bold: true
                             color: win.paper; opacity: reader.textOpacity } }
                // J15: fundo atual; clicar abre o menu de fundo
                Item {
                    visible: !win.full
                    width: 26; height: 26
                    Rectangle {
                        id: bgSwatch
                        anchors.centerIn: parent
                        width: 15; height: 15; radius: 3
                        color: reader.bgColor
                        border.width: 1
                        border.color: Qt.rgba(1, 1, 1, bgMa.containsMouse ? 0.8 : 0.35)
                        clip: true
                        Image {
                            anchors.fill: parent; anchors.margins: 1
                            visible: reader.bgImage !== ""
                            source: reader.bgImage
                            fillMode: Image.PreserveAspectCrop
                            sourceSize.width: 32; sourceSize.height: 32
                        }
                    }
                    MouseArea {
                        id: bgMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: bgMenu.popup(bgSwatch, 0, bgSwatch.height + 6)
                    }
                }
                Btn { visible: !win.full
                      tip: "Opacidade do fundo: " + Math.round(reader.bgOpacity * 100) + "%"
                      onClicked: reader.setBgOpacity(reader.bgOpacity >= 0.95 ? 0 : reader.bgOpacity + 0.15)
                      // quadrado com o preenchimento na opacidade atual do fundo
                      Rectangle { anchors.centerIn: parent; width: 14; height: 14; radius: 3
                                  color: Qt.rgba(0.95, 0.93, 0.89, 0.12 + 0.75 * reader.bgOpacity)
                                  border.width: 1.5; border.color: win.paper } }
            }
            Row {
                id: play
                anchors.right: parent.right
                y: bar.compact ? parent.height - height - 4 : (parent.height - height) / 2
                spacing: 2
                Btn { text: reader.speed.toFixed(2).replace(/0$/, "") + "×"
                      tip: "Velocidade (clique: mais rápido; botão direito: mais devagar)"
                      onClicked: reader.adjustSpeed(1)
                      onRightClicked: reader.adjustSpeed(-1) }
                Btn { id: backBtn; tip: "Voltar 10 s"; onClicked: reader.skip(-10)
                      Shape {
                          anchors.fill: parent
                          preferredRendererType: Shape.CurveRenderer
                          ShapePath {   // seta circular para a esquerda
                              strokeColor: backBtn.ink; strokeWidth: 1.5; fillColor: "transparent"
                              capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
                              startX: 9; startY: 2.5
                              PathArc { x: 14.6; y: 5.75; radiusX: 6.5; radiusY: 6.5
                                        useLargeArc: true; direction: PathArc.Counterclockwise }
                          }
                          ShapePath {
                              strokeColor: backBtn.ink; strokeWidth: 1.5; fillColor: "transparent"
                              capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
                              startX: 11.2; startY: 0.6
                              PathLine { x: 9; y: 2.5 }  PathLine { x: 11.2; y: 4.4 }
                          }
                      }
                      Text { anchors.centerIn: parent; anchors.verticalCenterOffset: 0.5
                             text: "10"; color: backBtn.ink
                             font.family: win.face; font.pixelSize: 7; font.bold: true } }
                Btn { id: playBtn; tip: reader.playing ? "Pausar" : "Tocar"; onClicked: reader.togglePlay()
                      Shape {
                          anchors.fill: parent
                          preferredRendererType: Shape.CurveRenderer
                          ShapePath {   // ▶
                              strokeColor: "transparent"
                              fillColor: reader.playing ? "transparent" : playBtn.ink
                              startX: 5; startY: 3
                              PathLine { x: 15; y: 9 } PathLine { x: 5; y: 15 } PathLine { x: 5; y: 3 }
                          }
                          ShapePath {   // ❚❚
                              strokeColor: "transparent"
                              fillColor: reader.playing ? playBtn.ink : "transparent"
                              startX: 4.5; startY: 3.5
                              PathLine { x: 7.5; y: 3.5 } PathLine { x: 7.5; y: 14.5 }
                              PathLine { x: 4.5; y: 14.5 } PathLine { x: 4.5; y: 3.5 }
                              PathMove { x: 10.5; y: 3.5 }
                              PathLine { x: 13.5; y: 3.5 } PathLine { x: 13.5; y: 14.5 }
                              PathLine { x: 10.5; y: 14.5 } PathLine { x: 10.5; y: 3.5 }
                          }
                      } }
                Btn { id: fwdBtn; tip: "Avançar 10 s"; onClicked: reader.skip(10)
                      Shape {
                          anchors.fill: parent
                          preferredRendererType: Shape.CurveRenderer
                          ShapePath {   // seta circular para a direita
                              strokeColor: fwdBtn.ink; strokeWidth: 1.5; fillColor: "transparent"
                              capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
                              startX: 9; startY: 2.5
                              PathArc { x: 3.4; y: 5.75; radiusX: 6.5; radiusY: 6.5
                                        useLargeArc: true; direction: PathArc.Clockwise }
                          }
                          ShapePath {
                              strokeColor: fwdBtn.ink; strokeWidth: 1.5; fillColor: "transparent"
                              capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
                              startX: 6.8; startY: 0.6
                              PathLine { x: 9; y: 2.5 }  PathLine { x: 6.8; y: 4.4 }
                          }
                      }
                      Text { anchors.centerIn: parent; anchors.verticalCenterOffset: 0.5
                             text: "10"; color: fwdBtn.ink
                             font.family: win.face; font.pixelSize: 7; font.bold: true } }
                Btn { id: pinBtn; active: reader.locked
                      tip: reader.locked ? "Janela fixa (clique para soltar)" : "Fixar a janela"
                      onClicked: reader.toggleLock()
                      Shape {   // alfinete: contorno solto, cheio quando fixa
                          anchors.fill: parent
                          preferredRendererType: Shape.CurveRenderer
                          ShapePath {
                              strokeColor: pinBtn.ink; strokeWidth: 1.5
                              fillColor: reader.locked ? pinBtn.ink : "transparent"
                              joinStyle: ShapePath.RoundJoin
                              startX: 5.5; startY: 2
                              PathLine { x: 12.5; y: 2 }  PathLine { x: 11; y: 3.5 }
                              PathLine { x: 11; y: 8 }    PathLine { x: 13.5; y: 11 }
                              PathLine { x: 4.5; y: 11 }  PathLine { x: 7; y: 8 }
                              PathLine { x: 7; y: 3.5 }   PathLine { x: 5.5; y: 2 }
                          }
                          ShapePath {   // agulha
                              strokeColor: pinBtn.ink; strokeWidth: 1.5; fillColor: "transparent"
                              capStyle: ShapePath.RoundCap
                              startX: 9; startY: 11; PathLine { x: 9; y: 16.5 }
                          }
                      } }
                // R10: com a janela solta, também a fixa
                Btn { id: passBtn; active: reader.passClicks
                      tip: "Deixar os cliques atravessarem a janela"
                      onClicked: reader.toggleClickThrough()
                      Shape {   // seta do mouse atravessando uma folha tracejada
                          anchors.fill: parent
                          preferredRendererType: Shape.CurveRenderer
                          ShapePath {
                              strokeColor: passBtn.ink; strokeWidth: 1.2; fillColor: "transparent"
                              strokeStyle: ShapePath.DashLine; dashPattern: [2, 1.5]
                              startX: 1.5; startY: 5
                              PathLine { x: 16.5; y: 5 }  PathLine { x: 16.5; y: 13 }
                              PathLine { x: 1.5; y: 13 }  PathLine { x: 1.5; y: 5 }
                          }
                          ShapePath {
                              strokeColor: passBtn.ink; strokeWidth: 1.3; fillColor: win.ink
                              joinStyle: ShapePath.RoundJoin
                              startX: 7; startY: 1.5
                              PathLine { x: 7; y: 14 }     PathLine { x: 9.7; y: 11.4 }
                              PathLine { x: 11.6; y: 16 }  PathLine { x: 13.4; y: 15.2 }
                              PathLine { x: 11.5; y: 10.7 } PathLine { x: 15; y: 10.7 }
                              PathLine { x: 7; y: 1.5 }
                          }
                      } }
                // J25: maximizar e restaurar, só no modo completo
                Btn { id: maxBtn; visible: win.full
                      tip: win.maxed ? "Restaurar" : "Maximizar"
                      onClicked: win.toggleMaximized()
                      Shape {
                          anchors.fill: parent
                          preferredRendererType: Shape.CurveRenderer
                          ShapePath {   // maximizada: o quadrado de trás, só a quina que aparece
                              strokeColor: win.maxed ? maxBtn.ink : "transparent"
                              strokeWidth: 1.4; fillColor: "transparent"
                              joinStyle: ShapePath.RoundJoin
                              startX: 6.5; startY: 4.5
                              PathLine { x: 6.5; y: 3 }
                              PathLine { x: 15; y: 3 }
                              PathLine { x: 15; y: 11.5 }
                              PathLine { x: 13.5; y: 11.5 }
                          }
                          ShapePath {   // o quadrado da frente (ou o único)
                              strokeColor: maxBtn.ink; strokeWidth: 1.4; fillColor: "transparent"
                              joinStyle: ShapePath.RoundJoin
                              startX: win.maxed ? 3 : 3.5; startY: win.maxed ? 6.5 : 3.5
                              PathLine { x: win.maxed ? 11.5 : 14.5; y: win.maxed ? 6.5 : 3.5 }
                              PathLine { x: win.maxed ? 11.5 : 14.5; y: win.maxed ? 15 : 14.5 }
                              PathLine { x: win.maxed ? 3 : 3.5; y: win.maxed ? 15 : 14.5 }
                              PathLine { x: win.maxed ? 3 : 3.5; y: win.maxed ? 6.5 : 3.5 }
                          }
                      } }
                Btn { id: quitBtn; tip: "Fechar"; onClicked: reader.quit()
                      Shape {
                          anchors.fill: parent
                          preferredRendererType: Shape.CurveRenderer
                          ShapePath {
                              strokeColor: quitBtn.ink; strokeWidth: 1.6; fillColor: "transparent"
                              capStyle: ShapePath.RoundCap
                              startX: 4.5; startY: 4.5;  PathLine { x: 13.5; y: 13.5 }
                              PathMove { x: 13.5; y: 4.5 } PathLine { x: 4.5; y: 13.5 }
                          }
                      } }
            }
        }

        // ------------------------------------------------------------ progresso (J10)
        Item {
            id: progress
            z: 2
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            anchors.leftMargin: panel.radius; anchors.rightMargin: panel.radius
            height: 10
            Rectangle {
                anchors.bottom: parent.bottom; anchors.bottomMargin: 4
                width: parent.width * reader.transcribedFraction; height: 2
                color: win.paper; opacity: 0.18
            }
            Rectangle {
                anchors.bottom: parent.bottom; anchors.bottomMargin: 4
                width: parent.width * reader.position / Math.max(1, reader.duration); height: 2
                color: win.ribbon; opacity: 0.85
            }
            MouseArea {
                id: progressMa
                anchors.fill: parent
                // J5: sobre a barra, o clique é da barra
                enabled: win.hovering && (!barHover.hovered || pressed)
                cursorShape: Qt.PointingHandCursor
                // clicar ou arrastar pula o áudio; cada pulo ressincroniza o texto (J4)
                function seekTo(x) { reader.seekFraction(Math.max(0, Math.min(1, x / width))) }
                onPressed: (m) => seekTo(m.x)
                onPositionChanged: (m) => { if (pressed) scrub.pendingX = m.x }
                // durante o arrasto, no máximo um pulo a cada 120 ms
                Timer {
                    id: scrub
                    property real pendingX: -1
                    interval: 120; repeat: true
                    running: progressMa.pressed
                    onTriggered: if (pendingX >= 0) { progressMa.seekTo(pendingX); pendingX = -1 }
                    onRunningChanged: if (!running && pendingX >= 0) { progressMa.seekTo(pendingX); pendingX = -1 }
                }
            }
        }

        // ------------------------------------------------------------ imagem (J6, G)
        Item {
            id: imagePanel
            anchors { right: parent.right; top: parent.top; bottom: bar.top }
            anchors.rightMargin: win.pad - 8
            width: reader.imagePanelWidth
            opacity: reader.image !== "" && width > 0 && !win.oneline ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }
            Image {
                anchors.centerIn: parent
                width: reader.imagePanelWidth
                height: reader.imagePanelHeight
                source: reader.image
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                smooth: true; mipmap: true
            }
        }

        // ------------------------------------------------------------ miniatura (J17)
        Item {
            id: thumb
            objectName: "thumb"
            z: 3
            visible: win.oneline && reader.image !== ""
            anchors.verticalCenter: list.verticalCenter
            anchors.right: parent.right
            anchors.rightMargin: win.pad - 8
            height: Math.min(win.lineH, 30); width: height * 1.4
            Rectangle {
                id: thumbFrame
                anchors.fill: parent
                radius: 5
                color: win.ink
                border.width: 1
                border.color: Qt.rgba(0.85, 0.70, 0.37, thumbHover.hovered || win.imgPinned ? 0.95 : 0.5)
                clip: true
                Image {
                    anchors.fill: parent; anchors.margins: 1
                    source: reader.image
                    fillMode: Image.PreserveAspectCrop
                    sourceSize.height: 96
                    asynchronous: true
                }
            }
            // pulso discreto quando a narração passa por uma imagem nova
            SequentialAnimation {
                id: pulse
                loops: 2
                NumberAnimation { target: thumbFrame; property: "scale"; to: 1.18; duration: 260; easing.type: Easing.OutQuad }
                NumberAnimation { target: thumbFrame; property: "scale"; to: 1.0; duration: 320; easing.type: Easing.InOutQuad }
            }
            HoverHandler { id: thumbHover; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: win.imgPinned = !win.imgPinned }
        }

        // ------------------------------------------------------------ altura do foco (J23)
        // marcador na parede esquerda, na altura da linha atual; arrastar move o foco (R15)
        Rectangle {
            id: focusGuide
            z: 3
            visible: focusMa.pressed
            x: focusHandle.x + focusHandle.width + 2
            width: parent.width - x - win.pad
            y: focusHandle.y + focusHandle.height / 2
            height: 1
            color: win.ribbon
            opacity: 0.35
        }
        Item {
            id: focusHandle
            objectName: "focusHandle"
            z: 4
            readonly property string tip: "altura do foco · " + Math.round(win.focusHeight * 100) + "%"
            // área onde o foco é medido: a lista no overlay, a página no modo completo
            readonly property real areaY: win.full ? page.y : list.y
            readonly property real areaH: win.full ? page.height : list.height
            // meia linha abaixo do topo da linha seguida
            readonly property real half: win.full ? 14 * reader.zoom : win.lineH / 2
            visible: !win.oneline && !reader.passClicks
            enabled: visible
            opacity: focusMa.pressed || focusMa.containsMouse ? 1 : win.barShown ? 0.6 : 0
            Behavior on opacity { NumberAnimation { duration: 180 } }
            width: 14; height: 22
            x: (win.pad - 8 - width) / 2           // no vão entre a parede e a fita
            y: areaY + areaH * win.focusHeight + half - height / 2
            Shape {                                // ponta de seta para a direita
                anchors.centerIn: parent
                width: 8; height: 12
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: "transparent"; fillColor: win.ribbon
                    startX: 0; startY: 0
                    PathLine { x: 8; y: 6 }
                    PathLine { x: 0; y: 12 }
                    PathLine { x: 0; y: 0 }
                }
            }
            MouseArea {
                id: focusMa
                anchors.fill: parent
                anchors.margins: -4
                hoverEnabled: true
                preventStealing: true
                cursorShape: Qt.SizeVerCursor
                onContainsMouseChanged: win.hoverTip(focusHandle, containsMouse && !pressed)
                property real grab: 0
                onPressed: (m) => {
                    win.hoverTip(focusHandle, false)
                    grab = mapToItem(focusHandle.parent, 0, m.y).y - focusHandle.y
                    win.dragFocus = win.focusHeight
                }
                onPositionChanged: (m) => {
                    if (!pressed) return
                    const y = mapToItem(focusHandle.parent, 0, m.y).y - grab
                              + focusHandle.height / 2 - focusHandle.half
                    const f = (y - focusHandle.areaY) / focusHandle.areaH
                    win.dragFocus = Math.max(0.2, Math.min(0.75, Math.round(f * 100) / 100))
                }
                onReleased: {
                    if (win.dragFocus >= 0) reader.setFocusHeight(win.dragFocus)
                    win.dragFocus = -1
                }
                onCanceled: win.dragFocus = -1
                onDoubleClicked: { win.dragFocus = -1; reader.setFocusHeight(0.4) }   // o soltar não desfaz
            }
        }

        // ------------------------------------------------------------ régua da linha (J24)
        // no alto da página: um marcador em cada ponta da linha do texto, ligados por um traço
        Item {
            id: ruler
            objectName: "lineRuler"
            z: 4
            readonly property var pg: page.item
            visible: win.full && !reader.passClicks && !!pg && pg.ready && pg.em > 0
            enabled: visible
            readonly property bool active: startGrip.pressed || endGrip.pressed || barGrip.pressed
            readonly property bool hovered: startGrip.hovered || endGrip.hovered || barGrip.hovered
            opacity: active || hovered ? 1 : win.barShown ? 0.6 : 0
            Behavior on opacity { NumberAnimation { duration: 180 } }
            // pontas da linha em px da janela (C16)
            readonly property var edges: visible ? reader.lineEdges(pg.boxW, pg.em, win.line[0], win.line[1]) : [0, 0]
            readonly property real x0: visible ? page.x + (pg.boxX + edges[0]) * reader.zoom : 0
            readonly property real x1: visible ? page.x + (pg.boxX + edges[1]) * reader.zoom : 0
            x: 0; y: page.y + 10
            width: parent.width; height: 12

            Rectangle {                            // traço entre as pontas
                x: ruler.x0; width: ruler.x1 - ruler.x0
                anchors.verticalCenter: parent.verticalCenter
                height: barGrip.hovered || barGrip.pressed ? 2 : 1
                color: win.ribbon; opacity: ruler.active || ruler.hovered ? 0.7 : 0.3
            }
            Repeater {                             // linhas-guia descendo das pontas
                model: 2
                Rectangle {
                    visible: ruler.active
                    x: (index === 0 ? ruler.x0 : ruler.x1) - 0.5
                    y: ruler.height
                    width: 1; height: page.height - ruler.y - ruler.height
                    color: win.ribbon; opacity: 0.35
                }
            }
            component Grip: Item {
                id: grip
                property string edge
                property string tip
                readonly property bool pressed: gripMa.pressed
                readonly property bool hovered: gripMa.containsMouse
                property real downX: 0
                property var start: null
                property var startEdges: null
                MouseArea {
                    id: gripMa
                    anchors.fill: parent
                    anchors.margins: -4
                    hoverEnabled: true
                    preventStealing: true
                    cursorShape: Qt.SizeHorCursor
                    onContainsMouseChanged: win.hoverTip(grip, containsMouse && !pressed)
                    onPressed: (m) => {
                        win.hoverTip(grip, false)
                        grip.downX = mapToItem(null, m.x, 0).x
                        grip.start = win.line
                        grip.startEdges = ruler.edges
                        win.dragLine = win.line
                    }
                    onPositionChanged: (m) => {
                        if (!pressed || !grip.start) return
                        const dx = (mapToItem(null, m.x, 0).x - grip.downX) / reader.zoom
                        const from = grip.edge === "right" ? grip.startEdges[1] : grip.startEdges[0]
                        win.dragLine = reader.moveLine(ruler.pg.boxW, ruler.pg.em, grip.start[0],
                                                       grip.start[1], grip.edge, from + dx)
                    }
                    onReleased: {
                        if (win.dragLine) reader.setLine(win.dragLine[0], win.dragLine[1])
                        win.dragLine = null
                    }
                    onCanceled: win.dragLine = null
                    onDoubleClicked: { win.dragLine = null; reader.setLine(39, 0.5) }   // o soltar não desfaz
                }
            }
            Grip {                                 // o traço: move a linha inteira
                id: barGrip
                edge: "both"; tip: "mover a linha"
                x: ruler.x0 + 10; width: Math.max(0, ruler.x1 - ruler.x0 - 20); height: parent.height
            }
            component Tip: Shape {                 // ponta de seta para baixo
                anchors.centerIn: parent
                width: 10; height: 7
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: "transparent"; fillColor: win.ribbon
                    startX: 0; startY: 0
                    PathLine { x: 10; y: 0 }
                    PathLine { x: 5; y: 7 }
                    PathLine { x: 0; y: 0 }
                }
            }
            Grip {
                id: startGrip
                edge: "left"; tip: "começo da linha"
                width: 12; height: parent.height
                x: ruler.x0 - width / 2
                Tip {}
            }
            Grip {
                id: endGrip
                edge: "right"; tip: "fim da linha"
                width: 12; height: parent.height
                x: ruler.x1 - width / 2
                Tip {}
            }
        }

        // ------------------------------------------------------------ soltar (J3)
        // cadeado aberto encostado na parede esquerda, na margem onde nunca há texto: na
        // altura da barra (escondida enquanto atravessa), ou no meio da linha da faixa (O)
        Item {
            id: releaseBtn
            z: 4
            visible: reader.passClicks
            width: 18; height: 24
            x: (win.pad - 8 - width) / 2           // no vão entre a parede e a fita
            y: win.oneline ? (reader.stripMargins(win.height)[0] + win.height
                              - reader.stripMargins(win.height)[1] - height) / 2
                           : bar.y + play.y + (play.height - height) / 2
            onYChanged: if (reader.passClicks) Qt.callLater(win.updateInputRegion)
            opacity: releaseMa.containsMouse ? 1 : 0.55
            Behavior on opacity { NumberAnimation { duration: 150 } }
            // cadeado aberto em vetor: haste em arco com a perna esquerda solta
            Shape {
                anchors.centerIn: parent
                width: 16; height: 18
                scale: win.oneline ? 0.75 : 1      // menor na faixa de uma linha
                preferredRendererType: Shape.CurveRenderer
                ShapePath {   // haste
                    strokeColor: win.ribbon; strokeWidth: 1.8
                    fillColor: "transparent"; capStyle: ShapePath.RoundCap
                    startX: 11.5; startY: 8.5
                    PathLine { x: 11.5; y: 4.6 }
                    PathArc { x: 4.5; y: 4.6; radiusX: 3.5; radiusY: 3.5; direction: PathArc.Counterclockwise }
                    PathLine { x: 4.5; y: 6.0 }
                }
                ShapePath {   // corpo
                    strokeColor: "transparent"; fillColor: win.ribbon
                    startX: 3.5; startY: 8.5
                    PathLine { x: 14.5; y: 8.5 }
                    PathArc { x: 16; y: 10; radiusX: 1.5; radiusY: 1.5 }
                    PathLine { x: 16; y: 16.5 }
                    PathArc { x: 14.5; y: 18; radiusX: 1.5; radiusY: 1.5 }
                    PathLine { x: 3.5; y: 18 }
                    PathArc { x: 2; y: 16.5; radiusX: 1.5; radiusY: 1.5 }
                    PathLine { x: 2; y: 10 }
                    PathArc { x: 3.5; y: 8.5; radiusX: 1.5; radiusY: 1.5 }
                }
                ShapePath {   // fechadura
                    strokeColor: win.ink; strokeWidth: 1.6
                    fillColor: "transparent"; capStyle: ShapePath.RoundCap
                    startX: 9; startY: 12
                    PathLine { x: 9; y: 14.5 }
                }
            }
            MouseArea {
                id: releaseMa
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: reader.toggleLock()      // soltar também desliga o atravessar (R10)
            }
        }

        // ------------------------------------------------------------ bordas (J2)
        component Edge: MouseArea {
            property int edges
            z: 3            // acima da faixa da barra: as bordas de baixo continuam redimensionando
            enabled: !reader.locked && !win.maxed     // J25: maximizada não redimensiona
            hoverEnabled: true
            onPressed: win.startSystemResize(edges)
        }
        Edge { edges: Qt.LeftEdge;   anchors { left: parent.left; top: parent.top; bottom: parent.bottom } width: 6; cursorShape: Qt.SizeHorCursor }
        Edge { edges: Qt.RightEdge;  anchors { right: parent.right; top: parent.top; bottom: parent.bottom } width: 6; cursorShape: Qt.SizeHorCursor }
        Edge { edges: Qt.TopEdge;    anchors { top: parent.top; left: parent.left; right: parent.right } height: 6; cursorShape: Qt.SizeVerCursor }
        Edge { edges: Qt.BottomEdge; anchors { bottom: parent.bottom; left: parent.left; right: parent.right } height: 6; cursorShape: Qt.SizeVerCursor }
        Edge { edges: Qt.TopEdge | Qt.LeftEdge;     anchors { top: parent.top; left: parent.left } width: 14; height: 14; cursorShape: Qt.SizeFDiagCursor }
        Edge { edges: Qt.BottomEdge | Qt.RightEdge; anchors { bottom: parent.bottom; right: parent.right } width: 14; height: 14; cursorShape: Qt.SizeFDiagCursor }
        Edge { edges: Qt.TopEdge | Qt.RightEdge;    anchors { top: parent.top; right: parent.right } width: 14; height: 14; cursorShape: Qt.SizeBDiagCursor }
        Edge { edges: Qt.BottomEdge | Qt.LeftEdge;  anchors { bottom: parent.bottom; left: parent.left } width: 14; height: 14; cursorShape: Qt.SizeBDiagCursor }
    }

    function hexOf(c) {
        const h = (v) => ("0" + Math.round(v * 255).toString(16)).slice(-2)
        return "#" + h(c.r) + h(c.g) + h(c.b)
    }
    // J16: seletores criados só quando usados; um problema no serviço de diálogos do
    // sistema nunca impede a janela de abrir
    Loader {
        id: textColorDlg
        active: false
        sourceComponent: ColorDialog {
            title: "Cor do texto"
            onAccepted: reader.setTextColor(win.hexOf(selectedColor))
        }
    }
    Loader {
        id: bgColorDlg
        active: false
        sourceComponent: ColorDialog {
            title: "Cor do fundo"
            onAccepted: { reader.setBgColor(win.hexOf(selectedColor)); reader.setBgImage("") }
        }
    }
    Loader {
        id: bgImageDlg
        active: false
        sourceComponent: FileDialog {
            title: "Imagem de fundo"
            nameFilters: ["Imagens (*.png *.jpg *.jpeg *.webp *.bmp *.gif)"]
            onAccepted: reader.setBgImage(selectedFile.toString())
        }
    }
    function openTextColor() {
        textColorDlg.active = true
        textColorDlg.item.selectedColor = reader.textColor
        textColorDlg.item.open()
    }
    function openBgColor() {
        bgColorDlg.active = true
        bgColorDlg.item.selectedColor = reader.bgColor
        bgColorDlg.item.open()
    }
    function openBgImage() {
        bgImageDlg.active = true
        bgImageDlg.item.open()
    }
    Menu {
        id: bgMenu
        objectName: "bgMenu"
        // janela própria: no modo de uma linha o menu não cabe na faixa nem na barra
        popupType: Popup.Window
        background: Rectangle {
            implicitWidth: 190
            color: win.ink; radius: 8
            border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.12)
        }
        delegate: MenuItem {
            id: mi
            contentItem: Text {
                text: mi.text
                color: win.paper; opacity: mi.enabled ? 1 : 0.4
                font.family: win.face; font.pixelSize: 13
                leftPadding: 4
            }
            background: Rectangle {
                radius: 6
                color: mi.highlighted ? Qt.rgba(0.85, 0.70, 0.37, 0.18) : "transparent"
            }
        }
        Action { text: "Cor do fundo…"
                 onTriggered: win.openBgColor() }
        Action { text: "Imagem de fundo…"; onTriggered: win.openBgImage() }
        Action { text: "Remover imagem"; enabled: reader.bgImage !== ""
                 onTriggered: reader.setBgImage("") }
    }

    // teclas da janela; com o foco na página do modo completo, elas chegam por ela (J22)
    function windowKey(name) {
        ({ "Space": () => reader.togglePlay(),
           "ArrowLeft": () => reader.skip(-10), "ArrowRight": () => reader.skip(10),
           "ArrowUp": () => reader.jumpBlock(-1), "ArrowDown": () => reader.jumpBlock(1),
           "Escape": () => { win.visible = false } })[name]()
    }
    Shortcut { sequence: "Space"; onActivated: win.windowKey("Space") }
    Shortcut { sequence: "Left"; onActivated: win.windowKey("ArrowLeft") }
    Shortcut { sequence: "Right"; onActivated: win.windowKey("ArrowRight") }
    Shortcut { sequence: "Up"; onActivated: win.windowKey("ArrowUp") }
    Shortcut { sequence: "Down"; onActivated: win.windowKey("ArrowDown") }
    Shortcut { sequence: "Escape"; onActivated: win.windowKey("Escape") }
}
