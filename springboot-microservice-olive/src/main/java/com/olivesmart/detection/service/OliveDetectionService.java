package com.olivesmart.detection.service;

import com.olivesmart.detection.dto.DetectedTreeDto;
import com.olivesmart.detection.dto.ParcelAnalysisRequest;
import com.olivesmart.detection.dto.ParcelAnalysisResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class OliveDetectionService {

    private final WebClient webClient;
    private final RayCastingGeofenceService geofenceService;

    public OliveDetectionService(
            WebClient.Builder webClientBuilder,
            RayCastingGeofenceService geofenceService,
            @Value("${olivesmart.ai.service-url:http://localhost:8000}") String aiServiceUrl
    ) {
        ExchangeStrategies exchangeStrategies = ExchangeStrategies.builder()
                .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(16 * 1024 * 1024))
                .build();
        this.webClient = webClientBuilder
                .baseUrl(aiServiceUrl)
                .exchangeStrategies(exchangeStrategies)
                .build();
        this.geofenceService = geofenceService;
    }

    public ParcelAnalysisResponse analyzeParcel(ParcelAnalysisRequest request) {
        if ("DEMO".equalsIgnoreCase(request.mode())) {
            return buildFallbackResponse(request, 0);
        }

        try {
            Map<String, Object> payload = new HashMap<>();
            payload.put("image_base64", request.imageBase64() != null ? request.imageBase64() : "");
            payload.put("vertices", request.vertices() != null ? request.vertices() : List.of());
            payload.put("gsd_meters_per_pixel", request.gsdMetersPerPixel() != null ? request.gsdMetersPerPixel() : 0.25);

            System.out.println("[OliveDetectionService] Calling Python AI Service with " + (request.vertices() != null ? request.vertices().size() : 0) + " vertices...");

            ParcelAnalysisResponse response = this.webClient.post()
                    .uri("/api/v1/analyze-parcel")
                    .bodyValue(payload)
                    .retrieve()
                    .bodyToMono(ParcelAnalysisResponse.class)
                    .timeout(Duration.ofSeconds(60))
                    .block();

            if (response == null || !response.success() || !"LIVE".equals(response.mode())
                    || !java.util.Set.of("YOLO", "OPENCV", "YOLO+OPENCV", "NONE").contains(response.engine() == null ? "" : response.engine())
                    || response.trees() == null
                    || response.totalTrees() != response.trees().size()
                    || (response.totalTrees() > 0 && "NONE".equals(response.engine()))
                    || response.trees().stream().anyMatch(t -> !java.util.Set.of("YOLO", "OPENCV").contains(t.source() == null ? "" : t.source())
                        || t.sources() == null || t.sources().isEmpty()
                        || !t.sources().contains(t.source())
                        || t.sources().stream().anyMatch(s -> !java.util.Set.of("YOLO", "OPENCV").contains(s)))) {
                return ParcelAnalysisResponse.failure("Réponse Python invalide ou analyse non réussie.");
            }
            System.out.println("[OliveDetectionService] Received response from Python AI Service: " + response.totalTrees() + " trees.");
            return response;
        } catch (org.springframework.web.reactive.function.client.WebClientResponseException ex) {
            try {
                var error = new com.fasterxml.jackson.databind.ObjectMapper()
                        .readTree(ex.getResponseBodyAsString()).path("error");
                if (error.isTextual()) {
                    return ParcelAnalysisResponse.failure(error.asText());
                }
            } catch (Exception ignored) {
                // Non-JSON HTTP errors keep the existing explicit failure contract.
            }
            return ParcelAnalysisResponse.failure("Erreur HTTP du service IA. Aucun autre modele utilise.");
        } catch (Exception ex) {
            System.err.println("[OliveDetectionService ERROR calling Python AI]: " + ex.getMessage());
            ex.printStackTrace();
            return ParcelAnalysisResponse.failure("Service IA indisponible ou analyse Python en échec. Aucun résultat simulé utilisé.");
        }
    }

    public Map<String, Object> modelStatus() {
        try {
            Map<String, Object> status = webClient.get().uri("/health").retrieve()
                    .bodyToMono(new org.springframework.core.ParameterizedTypeReference<Map<String, Object>>() {})
                    .timeout(Duration.ofSeconds(5)).block();
            Map<String, Object> result = new HashMap<>(status == null ? Map.of() : status);
            if (result.get("classes") instanceof Map<?, ?> classes) {
                result.put("classes", new java.util.ArrayList<>(classes.values()));
            }
            result.put("metricsStatus", "NON_VERIFIEES");
            result.put("healthMethod", "ExG : indicateur visuel heuristique, non valide comme diagnostic");
            return result;
        } catch (Exception ex) {
            return Map.of("model", "NON_CONFIRME", "modelLoaded", false,
                    "metricsStatus", "NON_VERIFIEES", "error", "Service IA indisponible ou modele non charge");
        }
    }

    private ParcelAnalysisResponse buildFallbackResponse(ParcelAnalysisRequest request, long elapsedMs) {
        if (!"DEMO".equalsIgnoreCase(request.mode())) {
            return ParcelAnalysisResponse.failure("Simulation interdite hors du mode DEMO.");
        }

        // Mode 1 : Profil Exact du Professeur (Capture 2 : 9 oliviers, 4 Sains, 3 Stress, 2 Suspects, 85.5% conf, 5.8m diam)
        if ("PROF_EXACT_9".equalsIgnoreCase(request.modelType())) {
            List<DetectedTreeDto> profTrees = List.of(
                new DetectedTreeDto(1, "SAIN", 0.91, 6.1, 31.63435, -7.96580),
                new DetectedTreeDto(2, "SAIN", 0.88, 5.9, 31.63420, -7.96550),
                new DetectedTreeDto(3, "SAIN", 0.87, 5.8, 31.63405, -7.96525),
                new DetectedTreeDto(4, "SAIN", 0.86, 5.7, 31.63385, -7.96500),
                new DetectedTreeDto(5, "STRESS", 0.84, 5.4, 31.63370, -7.96540),
                new DetectedTreeDto(6, "STRESS", 0.83, 5.3, 31.63350, -7.96520),
                new DetectedTreeDto(7, "STRESS", 0.82, 5.2, 31.63335, -7.96495),
                new DetectedTreeDto(8, "SUSPECT", 0.79, 4.8, 31.63320, -7.96510),
                new DetectedTreeDto(9, "SUSPECT", 0.78, 4.7, 31.63305, -7.96515)
            );
            return new ParcelAnalysisResponse(9, 4, 3, 2, 0.855, Math.max(213, elapsedMs), 5.8,
                    profTrees.stream().map(DetectedTreeDto::asDemo).toList())
                    .withTrace(true, "DEMO", "Aucun modèle (simulation)", "DEMO", null);
        }

        // Détection par défaut si l'IA distante est temporairement indisponible
        List<DetectedTreeDto> allTrees = buildRichMoroccanOrchard(request.vertices()).stream().map(DetectedTreeDto::asDemo).toList();
        int total = allTrees.size();
        int sains = (int) allTrees.stream().filter(t -> "SAIN".equalsIgnoreCase(t.healthStatus())).count();
        int stress = (int) allTrees.stream().filter(t -> "STRESS".equalsIgnoreCase(t.healthStatus())).count();
        int suspects = (int) allTrees.stream().filter(t -> "SUSPECT".equalsIgnoreCase(t.healthStatus())).count();
        double meanConf = allTrees.stream().mapToDouble(DetectedTreeDto::confidence).average().orElse(0.90);
        double meanDiam = allTrees.stream().mapToDouble(DetectedTreeDto::crownDiameterMeters).average().orElse(4.5);

        return new ParcelAnalysisResponse(
                total,
                sains,
                stress,
                suspects,
                Math.round(meanConf * 1000.0) / 1000.0,
                Math.max(180, elapsedMs),
                Math.round(meanDiam * 10.0) / 10.0,
                allTrees
        ).withTrace(true, "DEMO", "Aucun modèle (simulation)", "DEMO", null);
    }

    private List<DetectedTreeDto> buildRichMoroccanOrchard(List<com.olivesmart.detection.dto.GpsPoint> vertices) {
        if (vertices == null || vertices.size() < 3) {
            return List.of();
        }

        double minLat = vertices.stream().mapToDouble(com.olivesmart.detection.dto.GpsPoint::lat).min().orElse(31.63);
        double maxLat = vertices.stream().mapToDouble(com.olivesmart.detection.dto.GpsPoint::lat).max().orElse(31.64);
        double minLng = vertices.stream().mapToDouble(com.olivesmart.detection.dto.GpsPoint::lng).min().orElse(-7.97);
        double maxLng = vertices.stream().mapToDouble(com.olivesmart.detection.dto.GpsPoint::lng).max().orElse(-7.96);

        // Espacement agricole marocain : ~10m x 10m (~0.00009 deg lat, ~0.00010 deg lng)
        double stepLat = 0.00010;
        double stepLng = 0.00011;

        List<DetectedTreeDto> generated = new java.util.ArrayList<>();
        int id = 1;

        for (double lat = minLat + stepLat / 2; lat < maxLat; lat += stepLat) {
            for (double lng = minLng + stepLng / 2; lng < maxLng; lng += stepLng) {
                if (geofenceService.isPointInsidePolygon(lat, lng, vertices)) {
                    double rand = Math.random();
                    String health = rand > 0.15 ? "SAIN" : (rand > 0.05 ? "STRESS" : "SUSPECT");
                    double diam = Math.round((2.5 + Math.random() * 4.5) * 10.0) / 10.0;
                    double conf = Math.round((0.85 + Math.random() * 0.12) * 100.0) / 100.0;
                    generated.add(new DetectedTreeDto(id++, health, conf, diam, Math.round(lat * 100000.0) / 100000.0, Math.round(lng * 100000.0) / 100000.0));
                }
            }
        }
        return generated;
    }

}
