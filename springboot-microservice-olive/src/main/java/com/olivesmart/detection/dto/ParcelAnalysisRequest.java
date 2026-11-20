package com.olivesmart.detection.dto;

import java.util.List;

public record ParcelAnalysisRequest(
    String imageBase64,
    List<GpsPoint> vertices,
    Double gsdMetersPerPixel,
    String modelType,
    String mode // Only an explicit DEMO request may generate simulated trees.
) {
    public ParcelAnalysisRequest(String imageBase64, List<GpsPoint> vertices, Double gsdMetersPerPixel, String modelType) {
        this(imageBase64, vertices, gsdMetersPerPixel, modelType, "LIVE");
    }
    public ParcelAnalysisRequest {
        if (gsdMetersPerPixel == null || gsdMetersPerPixel <= 0) {
            gsdMetersPerPixel = 0.05; // 5.0 cm/px correspondant au zoom 17 Google Satellite
        }
    }
}
