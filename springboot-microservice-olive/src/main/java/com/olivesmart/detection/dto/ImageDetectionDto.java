package com.olivesmart.detection.dto;

import java.util.List;

public record ImageDetectionDto(Long id, List<Double> bboxPx, List<Double> centerPx,
        Double confidence, Integer classId, String className, String source) {}
