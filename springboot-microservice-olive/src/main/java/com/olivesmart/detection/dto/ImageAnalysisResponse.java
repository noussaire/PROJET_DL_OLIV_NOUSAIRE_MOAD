package com.olivesmart.detection.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;
import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public record ImageAnalysisResponse(boolean success, String mode, String engine, String imageId,
        String coordinateSystem, Integer imageWidth, Integer imageHeight, String format,
        Integer sourceWidth, Integer sourceHeight, Boolean orientationApplied, Boolean transparencyOnWhite,
        Integer totalDetections, Integer rawDetectionCount, Boolean roiApplied,
        List<ImageDetectionDto> detections, String model, String modelPath,
        Map<String, Object> inferenceParameters, Double inferenceTimeMs, Double totalTimeMs,
        List<String> warnings, String error) {
    public static ImageAnalysisResponse failure(String error) {
        return new ImageAnalysisResponse(false, "LIVE", "NONE", null, "IMAGE_PIXELS",
                null, null, null, null, null, null, null, 0, 0, null, List.of(),
                null, null, null, null, null, List.of(), error);
    }
}
