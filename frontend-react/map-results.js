(function (root) {
    'use strict';
    const modes = ['points', 'rectangles', 'both'];
    const colors = { SAIN: '#00e676', STRESS: '#ffb300', SUSPECT: '#ff5252' };
    const positive = value => Number.isFinite(value) && value > 0;
    const escape = value => String(value ?? '—').replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
    const number = value => Number.isFinite(value) ? value.toLocaleString('fr-FR', { maximumFractionDigits: 2 }) : '—';
    const exgNumber = value => Number.isFinite(value) ? String(value).replace('.', ',') : '—';
    const diameter = tree => positive(tree.crownDiameterMeters) ? tree.crownDiameterMeters : positive(tree.diam) ? tree.diam : null;
    const validScore = value => Number.isFinite(value) && value >= 0 && value <= 1;
    const confidence = tree => validScore(tree.confidence) ? tree.confidence : validScore(tree.conf) ? tree.conf : null;
    const categories = {
        HIGH: 'Végétation relativement plus verte selon ExG',
        INTERMEDIATE: 'Niveau ExG intermédiaire',
        LOW: 'Végétation relativement moins verte selon ExG'
    };
    const legacyCategories = { SAIN: 'HIGH', STRESS: 'INTERMEDIATE', SUSPECT: 'LOW' };
    function exgInfo(tree) {
        const metadata = tree.exgMetadata;
        const legacy = legacyCategories[tree.healthStatus ?? tree.health];
        if (metadata == null) return { value:null, label:categories[legacy] ?? 'Non renseignée',
            verified:false, note:'Valeur ExG et méthode non renseignées dans cette réponse.' };
        const validNumber = value => Number.isFinite(value) && value >= -510 && value <= 510;
        const value = validNumber(metadata.value) ? metadata.value : null;
        const thresholdsValid = validNumber(metadata.lowerThreshold) && validNumber(metadata.upperThreshold) &&
            metadata.lowerThreshold <= metadata.upperThreshold;
        const expected = value !== null && thresholdsValid ? value < metadata.lowerThreshold ? 'LOW' :
            value < metadata.upperThreshold ? 'INTERMEDIATE' : 'HIGH' : null;
        const sizeValid = Number.isInteger(metadata.populationSize) && metadata.populationSize >= 1;
        const methodValid = sizeValid && (metadata.populationSize > 5 ? metadata.classificationMethod === 'PERCENTILES_15_30' :
            metadata.classificationMethod === 'FIXED_SMALL_SAMPLE' && metadata.lowerThreshold === 0 && metadata.upperThreshold === 10);
        const windowValid = metadata.nominalWindowSize === 7 &&
            [metadata.sampleWidth, metadata.sampleHeight].every(n => Number.isInteger(n) && n >= 1 && n <= 7) &&
            metadata.samplePixelCount === metadata.sampleWidth * metadata.sampleHeight;
        const verified = value !== null && thresholdsValid && methodValid && windowValid &&
            metadata.category === expected && (!legacy || legacy === expected) &&
            metadata.formula === '2G-R-B' && metadata.rgbScale === 'UNNORMALIZED_0_255';
        return { value, label:verified ? categories[metadata.category] : 'Non vérifiable', verified,
            note:verified ? '' : 'Métadonnées ExG invalides ou incomplètes ; catégorie non vérifiable.', metadata };
    }
    function origin(tree) {
        const allowed = ['YOLO', 'OPENCV', 'DEMO'];
        const sources = Array.isArray(tree.sources) ? tree.sources.filter(s => allowed.includes(s)) : [];
        return sources.length ? sources.join(' + ') : allowed.includes(tree.source) ? tree.source : 'Non renseignée';
    }
    function bounds(tree) {
        const values = [tree.lat_min ?? tree.latMin, tree.lng_min ?? tree.lngMin,
            tree.lat_max ?? tree.latMax, tree.lng_max ?? tree.lngMax];
        if (values.every(Number.isFinite) && values[0] < values[2] && values[1] < values[3]) {
            return [[values[0], values[1]], [values[2], values[3]]];
        }
        const d = diameter(tree);
        if (!d || !Number.isFinite(tree.lat) || !Number.isFinite(tree.lng)) return null;
        // Existing meter-to-degree approximation, without display enlargement or an invented diameter.
        const halfLat = d / 2 / 111320;
        const halfLng = halfLat / Math.cos(tree.lat * Math.PI / 180);
        return [[tree.lat - halfLat, tree.lng - halfLng], [tree.lat + halfLat, tree.lng + halfLng]];
    }
    function details(tree) {
        const d = diameter(tree), score = confidence(tree), source = origin(tree);
        const demo = tree.source === 'DEMO';
        const uncalibrated = source.includes('OPENCV');
        const exg = exgInfo(tree);
        const scoreNature = demo ? 'score simulé' : uncalibrated ? source.includes('YOLO') ?
            'maximum des scores des candidats fusionnés YOLO/OpenCV ; non calibré' :
            'score OpenCV heuristique fixe (règle actuelle : 0,88), non calibré' :
            'score YOLO retenu (maximum en cas de fusion de candidats YOLO), sans calibration sanitaire';
        const method = exg.verified ? '<p>Calcul : moyenne sur ' + exg.metadata.sampleWidth + ' × ' + exg.metadata.sampleHeight +
            ' pixels (' + exg.metadata.samplePixelCount + ' pixels). Seuils : ' + exgNumber(exg.metadata.lowerThreshold) + ' / ' +
            exgNumber(exg.metadata.upperThreshold) + '. Population : ' + exg.metadata.populationSize + ' arbres hybrides. ' +
            (exg.metadata.classificationMethod === 'FIXED_SMALL_SAMPLE' ? 'Seuils fixes : série de cinq arbres ou moins.' : 'Percentiles 15 et 30 de cette analyse.') + '</p>' :
            '<p>' + escape(exg.note) + '</p>';
        const dimensions = [];
        if (d !== null) dimensions.push('Diamètre estimé : ' + number(d) + ' m');
        if (positive(tree.crownAreaM2)) dimensions.push('Surface estimée : ' + number(tree.crownAreaM2) + ' m²');
        if (positive(tree.widthMeters)) dimensions.push('Largeur estimée : ' + number(tree.widthMeters) + ' m');
        if (positive(tree.heightMeters)) dimensions.push('Hauteur estimée : ' + number(tree.heightMeters) + ' m');
        return '<div class="tree-result-detail">' +
            '<strong>Arbre #' + escape(tree.id) + '</strong>' +
            '<p>Source de détection : ' + escape(source) + (demo ? ' — simulation' : '') + '</p>' +
            '<p>Confiance de détection : ' + (score === null ? 'non renseignée' : number(score * 100) + ' %') +
            ' — ' + escape(scoreNature) + '</p>' +
            '<p>Valeur ExG calculée : ' + (exg.value === null ? 'non renseignée ou invalide' : exgNumber(exg.value)) + ' (RGB non normalisé).</p>' +
            '<p>Catégorie ExG : ' + escape(exg.label) + '</p>' + method +
            '<p>Position GPS estimée — Latitude : ' + escape(Number.isFinite(tree.lat) ? tree.lat.toFixed(6) : 'non renseignée') +
            ' · Longitude : ' + escape(Number.isFinite(tree.lng) ? tree.lng.toFixed(6) : 'non renseignée') + '</p>' +
            '<p>' + (dimensions.length ? dimensions.join(' · ') : 'Dimensions de couronne non renseignées.') + '</p>' +
            '<p>Dimensions estimées, pas une mesure terrain. Âge non déterminé.</p>' +
            '<p>' + (demo ? 'Indicateur simulé.' : 'Indicateur visuel ExG heuristique.') +
            ' Aucun diagnostic sanitaire validé ; la confiance de détection n’est pas une probabilité de santé.</p>' +
            '<a href="#exgMethodology" onclick="document.getElementById(\'exgMethodology\').open=true">Comprendre le calcul ExG</a></div>';
    }
    function counts(payload) {
        const metadata = payload?.analysisMetadata;
        const demo = payload?.mode === 'DEMO';
        const hybrid = Array.isArray(payload?.trees) ? payload.trees.length : null;
        let raw = !demo && Number.isInteger(metadata?.yoloInPolygonCount) && metadata.yoloInPolygonCount >= 0
            ? metadata.yoloInPolygonCount : null;
        // No coordinates are generated from a count. A complete raw list can supply a missing count.
        if (raw === null && !demo && Array.isArray(metadata?.yoloRawTrees) &&
                metadata.yoloRawTrees.every(t => typeof t.insideParcel === 'boolean')) {
            raw = metadata.yoloRawTrees.filter(t => t.insideParcel === true).length;
        }
        const coherent = hybrid !== null && payload.totalTrees === hybrid &&
            (demo || metadata?.hybridCount == null || metadata.hybridCount === hybrid);
        return { raw, hybrid, demo, coherent };
    }
    function createController(L, group, onSelect) {
        let mode = 'points', trees = [], selectedId = null;
        // A single Canvas renderer avoids hundreds of SVG/DOM nodes. Pixel radius stays stable on zoom.
        const renderer = L.canvas({ padding: 0.5, tolerance: 6 });
        const entries = new Map();
        function select(id) {
            selectedId = id;
            entries.forEach((entry, key) => {
                const selected = key === id;
                if (entry.point) {
                    entry.point.setStyle({ color: '#ffffff', weight: selected ? 2 : 1, fillOpacity: 1 });
                    entry.point.setRadius(selected ? 5.5 : 3.5);
                }
                if (entry.rect) entry.rect.setStyle({ weight: selected ? 2.5 : 1, fillOpacity: selected ? 0.12 : 0.025 });
                if (selected) (entry.point || entry.rect)?.bringToFront();
            });
        }
        function render(nextTrees, nextSelected = selectedId) {
            trees = nextTrees;
            group.clearLayers();
            entries.clear();
            for (const tree of trees) {
                if (!Number.isFinite(tree.lat) || !Number.isFinite(tree.lng)) continue;
                const color = colors[tree.healthStatus ?? tree.health] || '#64748b';
                const entry = { point: null, rect: null };
                const box = bounds(tree);
                if (mode !== 'points' && box) entry.rect = L.rectangle(box, {
                    renderer, color, weight: 1, fillColor: color, fillOpacity: 0.025, bubblingMouseEvents: false
                }).addTo(group);
                if (mode !== 'rectangles') entry.point = L.circleMarker([tree.lat, tree.lng], {
                    renderer, radius: 3.5, color: '#ffffff', weight: 1, fillColor: color, fillOpacity: 1,
                    bubblingMouseEvents: false
                }).addTo(group);
                const tooltip = '<strong>Arbre #' + escape(tree.id) + '</strong> · ' + escape(origin(tree)) +
                    '<br>ExG heuristique : ' + escape(exgInfo(tree).label);
                for (const layer of [entry.rect, entry.point].filter(Boolean)) {
                    layer.bindTooltip(tooltip, { sticky: true, opacity: 0.95 });
                    layer.on('click', () => onSelect(tree.id));
                }
                entries.set(tree.id, entry);
            }
            select(nextSelected);
        }
        function setMode(value) {
            if (!modes.includes(value)) throw new Error('Mode cartographique inconnu');
            mode = value;
            render(trees);
        }
        return { render, select, setMode, entries, getMode: () => mode };
    }
    const api = { bounds, diameter, confidence, origin, details, counts, createController, exgInfo };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.OliveMapResults = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
