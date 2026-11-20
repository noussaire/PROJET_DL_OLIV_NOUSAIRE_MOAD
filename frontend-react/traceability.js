(function (root) {
    'use strict';
    function validate(payload, requestedMode = 'LIVE') {
        if (!payload || payload.success !== true) {
            throw new Error(payload?.error || 'Analyse échouée : aucun résultat valide reçu.');
        }
        const demo = requestedMode === 'DEMO';
        const allowed = demo ? ['DEMO'] : ['YOLO', 'OPENCV'];
        const engines = demo ? ['DEMO'] : ['NONE', 'YOLO', 'OPENCV', 'YOLO+OPENCV'];
        if (payload.mode !== requestedMode || !engines.includes(payload.engine)
                || !Array.isArray(payload.trees) || payload.totalTrees !== payload.trees.length
                || (payload.trees.length > 0 && payload.engine === 'NONE')
                || payload.trees.some(t => !allowed.includes(t.source)
                    || !Array.isArray(t.sources) || !t.sources.length
                    || !t.sources.includes(t.source) || t.sources.some(s => !allowed.includes(s)))) {
            throw new Error('Provenance invalide. Aucun résultat affiché ; vérifier les versions des services.');
        }
        return payload;
    }
    async function analyze(fetchImpl, vertices, mode = 'LIVE') {
        let response;
        try {
            response = await fetchImpl('http://localhost:8080/api/v1/parcelles/analyser', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ modelType: 'SERVER_CONFIGURED', mode, vertices, gsdMetersPerPixel: 0.05 })
            });
        } catch (_) {
            throw new Error('Spring Boot indisponible (:8080). Vérifier les services puis réessayer.');
        }
        let payload;
        try { payload = await response.json(); }
        catch (_) { throw new Error('Réponse du service illisible. Aucun résultat affiché.'); }
        if (!response.ok) throw new Error(payload.error || 'Analyse refusée par le service IA.');
        return validate(payload, mode);
    }
    function requireDemo(enabled) {
        if (!enabled) throw new Error('Cette fonctionnalité est une simulation. Activer explicitement le mode DEMO.');
    }
    const api = { validate, analyze, requireDemo };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.OliveTrace = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
