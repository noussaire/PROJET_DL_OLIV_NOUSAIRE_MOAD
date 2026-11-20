package com.olivesmart.detection.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record ParcelAnalysisResponse(
    int totalTrees,
    int healthyCount,
    int stressCount,
    int suspectCount,
    double meanConfidence,
    long inferenceTimeMs,
    double meanCrownDiameterMeters,
    List<DetectedTreeDto> trees,
    int youngCount,
    int adultCount,
    int centenaryCount,
    double totalCanopyAreaM2,
    String droneVideoStatus,
    boolean success,
    String engine,
    String model,
    String mode,
    String error,
    java.util.Map<String, Object> analysisMetadata
) {
    // Preserve the previous canonical constructor and all older JSON fields.
    public ParcelAnalysisResponse(int totalTrees, int healthyCount, int stressCount, int suspectCount,
            double meanConfidence, long inferenceTimeMs, double meanCrownDiameterMeters,
            List<DetectedTreeDto> trees, int youngCount, int adultCount, int centenaryCount,
            double totalCanopyAreaM2, String droneVideoStatus, boolean success, String engine,
            String model, String mode, String error) {
        this(totalTrees, healthyCount, stressCount, suspectCount, meanConfidence, inferenceTimeMs,
                meanCrownDiameterMeters, trees, youngCount, adultCount, centenaryCount,
                totalCanopyAreaM2, droneVideoStatus, success, engine, model, mode, error, null);
    }
    public ParcelAnalysisResponse(int totalTrees, int healthyCount, int stressCount, int suspectCount,
            double meanConfidence, long inferenceTimeMs, double meanCrownDiameterMeters,
            List<DetectedTreeDto> trees, int youngCount, int adultCount, int centenaryCount,
            double totalCanopyAreaM2, String droneVideoStatus) {
        this(totalTrees, healthyCount, stressCount, suspectCount, meanConfidence, inferenceTimeMs,
                meanCrownDiameterMeters, trees, youngCount, adultCount, centenaryCount, totalCanopyAreaM2,
                droneVideoStatus, false, "NONE", "NON_CONFIRME", "LIVE", null);
    }
    // Constructeur rétro-compatible à 8 arguments
    public ParcelAnalysisResponse(
        int totalTrees,
        int healthyCount,
        int stressCount,
        int suspectCount,
        double meanConfidence,
        long inferenceTimeMs,
        double meanCrownDiameterMeters,
        List<DetectedTreeDto> trees
    ) {
        this(
            totalTrees,
            healthyCount,
            stressCount,
            suspectCount,
            meanConfidence,
            inferenceTimeMs,
            meanCrownDiameterMeters,
            trees,
            (int) (trees != null ? trees.stream().filter(t -> "JEUNE".equalsIgnoreCase(t.ageCategory())).count() : 0),
            (int) (trees != null ? trees.stream().filter(t -> "ADULTE".equalsIgnoreCase(t.ageCategory())).count() : 0),
            (int) (trees != null ? trees.stream().filter(t -> "CENTENAIRE".equalsIgnoreCase(t.ageCategory())).count() : 0),
            trees != null ? Math.round(trees.stream().mapToDouble(DetectedTreeDto::crownAreaM2).sum() * 10.0) / 10.0 : 0.0,
            "NON_TRAITE", false, "NONE", "NON_CONFIRME", "LIVE", null
        );
    }

    public ParcelAnalysisResponse withTrace(boolean succeeded, String usedEngine, String usedModel, String analysisMode, String message) {
        return new ParcelAnalysisResponse(totalTrees, healthyCount, stressCount, suspectCount,
                meanConfidence, inferenceTimeMs, meanCrownDiameterMeters, trees,
                youngCount, adultCount, centenaryCount, totalCanopyAreaM2, droneVideoStatus,
                succeeded, usedEngine, usedModel, analysisMode, message, analysisMetadata);
    }

    public static ParcelAnalysisResponse failure(String message) {
        return new ParcelAnalysisResponse(0, 0, 0, 0, 0, 0, 0, List.of())
                .withTrace(false, "NONE", "NON_CONFIRME", "LIVE", message);
    }
}
