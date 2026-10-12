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
    property bool browsing: false          // J4: texto solto da narração (roda do mouse)
    function resync() {                    // J4: volta o texto para a palavra narrada
        browsing = false
        list.requestFollow(true)
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
    minimumWidth: 320; minimumHeight: reader.onelineHeight
    // O2/J14: o modo de uma linha é consequência da altura da janela
    readonly property bool oneline: height < reader.onelineThreshold
    readonly property real lineH: reader.linePitch          // O1: medida na tela
    visible: true
    color: "transparent"
    title: reader.bookTitle
    // J1/R10: solta = janela comum; fixa = por cima das outras; J3: cliques atravessam
    // (o atravessar cliques usa a forma de entrada do X11, para o botão "soltar" seguir clicável)
    flags: Qt.Window | Qt.FramelessWindowHint
           | (reader.onTop ? Qt.WindowStaysOnTopHint : 0)

    Component.onCompleted: {
        const g = reader.geometry
        if (g.length === 4) {
            if (g[0] >= 0) { x = g[0]; y = g[1]; width = g[2] }
            height = g[3]
        }
        lastLine = reader.linePitch
        if (reader.passClicks) {                 // abriu já atravessando: aplica e avisa
            Qt.callLater(updateInputRegion)
        }
        Qt.callLater(syncImage)                  // abriu dentro da janela de uma imagem (R5)
    }
    onXChanged: saveGeo.restart()
    onYChanged: saveGeo.restart()
    onWidthChanged: { saveGeo.restart(); if (reader.passClicks) Qt.callLater(updateInputRegion) }
    onHeightChanged: saveGeo.restart()
    Timer { id: saveGeo; interval: 600; onTriggered: reader.saveGeometry(win.x, win.y, win.width, win.height) }

    Connections {
        target: reader
        function onVisibilityToggleRequested() { win.visible = !win.visible }
        function onJumped() { win.resync() }          // J4: pulo no áudio ressincroniza
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

    // G: a janela cresce para a direita para a imagem e depois volta
    property string shownImage: ""          // imagem com espaço aberto ao lado do texto
    function syncImage() {
        // pela altura, e não por `oneline`: na abertura a ligação ainda não se atualizou
        const many = win.height >= reader.onelineThreshold
        const want = reader.image !== "" && many ? reader.image : ""
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
    Connections {
        target: reader
        function onImageChanged() { win.syncImage() }
    }

    // ------------------------------------------------------------ painel
    Rectangle {
        id: panel
        anchors.fill: parent
        radius: 14
        readonly property color bgC: reader.bgColor
        color: reader.bgImage !== "" ? "transparent" : Qt.rgba(bgC.r, bgC.g, bgC.b, reader.bgOpacity)

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
            visible: reader.bgImage !== ""
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
        ListView {
            id: list
            objectName: "lst"
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
                                 + (thumb.visible ? thumb.width + 10 : 0)       // J17
            clip: true
            interactive: false
            model: blocks
            spacing: 0
            header: Item { height: win.oneline ? 0 : list.height * 0.40 }
            footer: Item { height: win.oneline ? list.height : list.height * 0.60 }

            NumberAnimation on contentY {
                id: scrollAnim
                running: false
                duration: 450
                easing.type: Easing.OutCubic
            }

            // J4: mantém a linha da palavra atual a 40% da altura
            // Nunca reposiciona a lista de dentro de um tratador de delegate: isso pode destruir
            // o delegate no meio do próprio código (segfault em pulos rápidos). Toda chamada é
            // adiada para o laço de eventos e várias no mesmo ciclo viram uma só.
            property bool followAnimated: false
            function requestFollow(animated) {
                followAnimated = animated
                Qt.callLater(list.follow)
            }
            function follow() {
                let animated = followAnimated
                const r = reader.currentRow
                if (win.browsing || r < 0) return
                let item = itemAtIndex(r)
                if (!item) {
                    positionViewAtIndex(r, ListView.Beginning)
                    item = itemAtIndex(r)
                    animated = false
                    if (!item) return
                }
                const anchorY = win.oneline ? 0 : height * 0.40
                const target = item.y + item.lineY - anchorY
                if (Math.abs(target - contentY) < 1) return
                if (animated) {
                    scrollAnim.stop()
                    scrollAnim.from = contentY
                    scrollAnim.to = target
                    scrollAnim.start()
                } else {
                    contentY = target
                }
            }
            onHeightChanged: requestFollow(false)
            // a lista estima a altura dos parágrafos ainda não criados; quando um parágrafo
            // acima é criado de verdade, tudo se desloca e o enquadramento precisa ser refeito
            onOriginYChanged: requestFollow(scrollAnim.running)
            onContentHeightChanged: requestFollow(scrollAnim.running)
            Component.onCompleted: requestFollow(false)

            delegate: Item {
                id: row
                required property int index
                required property string kind
                required property string html
                required property bool shown
                readonly property bool current: index === reader.currentRow
                // espaçamento no próprio HTML: texto visível e medidor têm o mesmo layout
                readonly property string rich: '<div style="line-height:128%">' + html + '</div>'
                // y da linha da palavra atual dentro do parágrafo
                readonly property real lineY: current && meter.item ? meter.item.y + meter.item.lineY : 0
                onLineYChanged: if (current) list.requestFollow(true)
                onCurrentChanged: if (current) list.requestFollow(true)
                width: list.width
                height: shown ? body.implicitHeight + gap : 0
                visible: shown
                readonly property real gap: kind === "h" ? reader.fontSize * 0.9 : reader.fontSize * 0.7

                Text {
                    id: body
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
            height: win.dock
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
            height: 34
            opacity: win.barShown ? 1 : 0
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
                PropertyChanges { target: bar; width: controls.implicitWidth + 8 }
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
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.right: controls.left
                anchors.rightMargin: 12
                elide: Text.ElideRight
                visible: !win.oneline
                text: reader.chapterTitle
                color: win.paper; opacity: 0.6
                font.family: win.face; font.pixelSize: 12
            }

            Row {
                id: controls
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                component Btn: Text {
                    id: btn
                    signal clicked()
                    property bool active: false
                    width: Math.max(28, implicitWidth + 12); height: 26
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    color: active ? win.ribbon : win.paper
                    opacity: ma.containsMouse ? 1 : 0.7
                    font.family: win.face; font.pixelSize: 13
                    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor; onClicked: btn.clicked() }
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

                Btn { text: "A−"; onClicked: reader.adjustFont(-2) }
                Btn { text: "A+"; onClicked: reader.adjustFont(2) }
                // R8: cor do texto (abre o seletor) e opacidade do texto
                Item {
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
                Btn { text: "Aa " + Math.round(reader.textOpacity * 100) + "%"
                      onClicked: reader.setTextOpacity(reader.textOpacity <= 0.41 ? 1.0 : reader.textOpacity - 0.15) }
                // J15: fundo atual; clicar abre o menu de fundo
                Item {
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
                Btn { text: "◐ " + Math.round(reader.bgOpacity * 100) + "%"
                      onClicked: reader.setBgOpacity(reader.bgOpacity >= 0.95 ? 0 : reader.bgOpacity + 0.15) }
                Btn { text: reader.speed.toFixed(2).replace(/0$/, "") + "×"
                      onClicked: reader.adjustSpeed(1)
                      MouseArea { anchors.fill: parent; acceptedButtons: Qt.RightButton
                                  onClicked: reader.adjustSpeed(-1) } }
                Btn { text: "‹‹"; onClicked: reader.skip(-10) }
                Btn { text: reader.playing ? "pausar" : "tocar"; onClicked: reader.togglePlay() }
                Btn { text: "››"; onClicked: reader.skip(10) }
                Btn { text: reader.locked ? "fixa" : "fixar"; active: reader.locked
                      onClicked: reader.toggleLock() }
                Btn { text: "atravessar"; visible: reader.locked; active: reader.clickThrough
                      onClicked: reader.toggleClickThrough() }
                Btn { text: "✕"; onClicked: reader.quit() }
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

        // ------------------------------------------------------------ soltar (J3)
        // cadeado aberto, na margem direita (onde nunca há texto)
        Item {
            id: releaseBtn
            z: 4
            visible: reader.passClicks
            anchors { top: parent.top; right: parent.right; topMargin: 7; rightMargin: 6 }
            width: 18; height: 20
            opacity: releaseMa.containsMouse ? 1 : 0.55
            Behavior on opacity { NumberAnimation { duration: 150 } }
            // cadeado aberto em vetor: haste em arco com a perna esquerda solta
            Shape {
                anchors.centerIn: parent
                width: 16; height: 18
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
                anchors.margins: -3
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: reader.toggleLock()      // soltar também desliga o atravessar (R10)
            }
        }

        // ------------------------------------------------------------ bordas (J2)
        component Edge: MouseArea {
            property int edges
            z: 3            // acima da faixa da barra: as bordas de baixo continuam redimensionando
            enabled: !reader.locked
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

    Shortcut { sequence: "Space"; onActivated: reader.togglePlay() }
    Shortcut { sequence: "Left"; onActivated: reader.skip(-10) }
    Shortcut { sequence: "Right"; onActivated: reader.skip(10) }
    Shortcut { sequence: "Up"; onActivated: reader.jumpBlock(-1) }
    Shortcut { sequence: "Down"; onActivated: reader.jumpBlock(1) }
    Shortcut { sequence: "Escape"; onActivated: win.visible = false }
}
