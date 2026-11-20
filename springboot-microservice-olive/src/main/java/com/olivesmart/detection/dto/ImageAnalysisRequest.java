package com.olivesmart.detection.dto;

import java.util.List;

public record ImageAnalysisRequest(String imageBase64, String imageId, Integer imageWidth,
        Integer imageHeight, List<PixelPoint> roiPx, String mode) {
    public record PixelPoint(Double x, Double y) {}
}
