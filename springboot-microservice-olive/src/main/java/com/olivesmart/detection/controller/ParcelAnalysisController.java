package com.olivesmart.detection.controller;

import com.olivesmart.detection.dto.ParcelAnalysisRequest;
import com.olivesmart.detection.dto.ParcelAnalysisResponse;
import com.olivesmart.detection.service.OliveDetectionService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * Contrôleur REST pour l'analyse des parcelles oléicoles
 * Répond directement au clic "6 points tracés — Analyser avec YOLO"
 */
@RestController
@RequestMapping("/api/v1/parcelles")
@CrossOrigin(origins = "*")
public class ParcelAnalysisController {

    private final OliveDetectionService detectionService;

    public ParcelAnalysisController(OliveDetectionService detectionService) {
        this.detectionService = detectionService;
    }

    @PostMapping("/analyser")
    public ResponseEntity<ParcelAnalysisResponse> analyserParcelle(@RequestBody ParcelAnalysisRequest request) {
        // Exécute l'inférence YOLO et le Geofencing cadastral
        ParcelAnalysisResponse response = detectionService.analyzeParcel(request);
        return ResponseEntity.status(response.success() ? 200 : 502).body(response);
    }

    @PostMapping("/analyser-video")
    public ResponseEntity<ParcelAnalysisResponse> analyserVideoDrone(@RequestBody ParcelAnalysisRequest request) {
        return ResponseEntity.status(501).body(ParcelAnalysisResponse.failure("Analyse vidéo réelle non implémentée. Utiliser la démonstration explicitement."));
    }

    @GetMapping("/metriques-modele")
    public ResponseEntity<java.util.Map<String, Object>> getModelMetrics() {
        return ResponseEntity.ok(detectionService.modelStatus());
    }
}
