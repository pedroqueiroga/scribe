// Modo completo (specs/completo.md C8, C13, C14; janela.md J20, J22). A interface chama
// scribe.set(...) a cada palavra nova; a página fala com ela por console.log("scribe:...").
// As palavras não são elementos: cada bloco guarda em data-w os trechos delas no texto dele
// ("id:início:fim ..."), e o marca-texto é pintado com a CSS Custom Highlight API.
(() => {
    const B = new Map()                       // id do bloco → elemento
    for (const e of document.querySelectorAll("[data-b]")) B.set(+e.dataset.b, e)

    const send = (m) => console.log("scribe:" + m)

    // palavras de um bloco, lidas só quando preciso: [{id, s, e}]
    const parsed = new WeakMap()
    function words(el) {
        if (!parsed.has(el))
            parsed.set(el, (el.dataset.w || "").split(" ").filter(Boolean).map((x) => {
                const [id, s, e] = x.split(":").map(Number)
                return { id, s, e }
            }))
        return parsed.get(el)
    }
    // posição (em caracteres do texto do bloco) → ponto no DOM, e o caminho inverso
    function textNodes(el) {
        const out = [], it = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
        for (let n = it.nextNode(); n; n = it.nextNode()) out.push(n)
        return out
    }
    function range(el, s, e) {
        const r = document.createRange()
        let pos = 0, started = false
        for (const n of textNodes(el)) {
            const len = n.length
            if (!started && s <= pos + len) { r.setStart(n, s - pos); started = true }
            if (started && e <= pos + len) { r.setEnd(n, e - pos); return r }
            pos += len
        }
        return started ? r : null
    }
    function offsetIn(el, node, offset) {
        let pos = 0
        for (const n of textNodes(el)) {
            if (n === node) return pos + offset
            pos += n.length
        }
        return -1
    }

    const now = new Highlight(), past = new Highlight(), dim = new Highlight()
    CSS.highlights.set("scribe-now", now)
    CSS.highlights.set("scribe-past", past)
    CSS.highlights.set("scribe-dim", dim)

    let cur = { word: null, row: -1 }
    let nowRange = null
    let focus = -1
    let browsing = false
    let synced = true

    // C13: marca-texto forte na palavra atual e leve nas já ditas do bloco atual (uma faixa
    // só, do começo da primeira até o fim da anterior, cobrindo os espaços)
    function set(word, row, isSynced, animated) {
        if (word !== cur.word || row !== cur.row) {
            now.clear(); past.clear(); dim.clear()
            nowRange = null
            const el = B.get(row)
            const ws = el ? words(el) : []
            const k = ws.findIndex((w) => w.id === word)
            if (k >= 0) {
                nowRange = range(el, ws[k].s, ws[k].e)
                if (k > 0) {
                    const r = range(el, ws[0].s, ws[k - 1].e)
                    if (r) past.add(r)
                }
            }
            cur = { word, row }
        }
        synced = isSynced
        now.clear(); dim.clear()
        if (nowRange) (synced ? now : dim).add(nowRange)
        follow(animated)
    }

    function setFocus(row) { focus = row; follow(true) }

    // R15: altura do foco, em fração da altura da página; o espaço antes e depois do livro
    // acompanha, para a primeira e a última linha também chegarem a ela (J23)
    let anchor = 0.4
    function setAnchor(f) {
        anchor = f
        document.documentElement.style.setProperty("--scribe-focus", f)
        follow(false)
    }

    // J20: a linha da palavra atual na altura do foco; a imagem em foco, centralizada (G10)
    function target() {
        const img = focus >= 0 ? B.get(focus) : null
        const box = img || nowRange || B.get(cur.row)
        if (!box) return null
        const r = box.getBoundingClientRect()
        const y = img ? r.top + r.height / 2 - innerHeight / 2 : r.top - innerHeight * anchor
        return { y: Math.max(0, scrollY + y), slow: !!img }
    }

    // a rolagem persegue o alvo quadro a quadro: se uma imagem acima termina de carregar
    // no meio do caminho, o alvo se move e a rolagem segue sem solavanco
    let anim = 0, last = 0
    function follow(animated) {
        if (browsing) return
        const t = target()
        if (!t) return
        if (!animated) { cancelAnimationFrame(anim); anim = 0; scrollTo(0, t.y); return }
        if (!anim) { last = performance.now(); anim = requestAnimationFrame(step) }
    }
    function step(time) {
        anim = 0
        const t = target()
        if (browsing || !t) return
        const dt = Math.min(64, time - last); last = time
        const d = t.y - scrollY
        if (Math.abs(d) < 0.5) { scrollTo(0, t.y); return }
        scrollTo(0, scrollY + d * (1 - Math.exp(-dt / (t.slow ? 380 : 130))))
        anim = requestAnimationFrame(step)
    }

    // J20: rolar à mão solta a página da narração
    function release() {
        if (!browsing) { browsing = true; send("browse") }
    }
    addEventListener("wheel", release, { passive: true })
    // J22: as teclas da janela valem com o foco na página; as de página rolam e soltam
    const WINDOW_KEYS = [" ", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Escape"]
    addEventListener("keydown", (e) => {
        if (e.ctrlKey || e.altKey || e.metaKey) return
        if (WINDOW_KEYS.includes(e.key)) {
            e.preventDefault()
            send("key:" + (e.key === " " ? "Space" : e.key))
        } else if (["PageUp", "PageDown", "Home", "End"].includes(e.key)) {
            release()
        }
    })
    addEventListener("mousedown", (e) => {        // barra de rolagem
        if (e.clientX >= document.documentElement.clientWidth) release()
    })
    function resync() { browsing = false; follow(true) }

    // C14: a palavra sob o clique, pelo ponto do texto; J22: links internos rolam até o
    // ponto, externos não abrem nada
    addEventListener("click", (e) => {
        const a = e.target.closest("a[href]")
        if (a) {
            if (a.getAttribute("href").startsWith("#")) release()
            else e.preventDefault()
            return
        }
        const p = document.caretPositionFromPoint(e.clientX, e.clientY)
        if (!p || p.offsetNode.nodeType !== Node.TEXT_NODE) return
        const el = p.offsetNode.parentElement.closest("[data-w]")
        if (!el) return
        const at = offsetIn(el, p.offsetNode, p.offset)
        // o caret cai entre letras: vale a palavra que contém o ponto, ou a que começa nele
        const w = words(el).find((w) => w.s <= at && at < w.e) || words(el).find((w) => w.e === at)
        if (w) send("seek:" + w.id)
    })
    addEventListener("resize", () => follow(false))
    // imagens e fontes que terminam de carregar mudam a altura do que está acima da
    // palavra: o enquadramento é refeito na hora, para ela não sair do lugar (J21)
    new ResizeObserver(() => { if (!anim) follow(false) }).observe(document.body)

    window.scribe = { set, setFocus, setAnchor, resync }
    send("ready")
})()
