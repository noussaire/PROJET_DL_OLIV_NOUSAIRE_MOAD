package com.olivesmart.detection.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.olivesmart.detection.dto.DetectedTreeDto;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ExgMetadataTest {
    @Test void valuesThresholdsAndWindowSurviveJavaRoundTripWithoutLegacyChanges() throws Exception {
        var mapper = new ObjectMapper();
        var dto = mapper.readValue("""
            {"id":1,"healthStatus":"STRESS","confidence":0.88,"source":"OPENCV","sources":["OPENCV"],
             "lat":31.6338,"lng":-7.9653,"crownDiameterMeters":5,
             "exgMetadata":{"value":0.0,"category":"INTERMEDIATE","lowerThreshold":0.0,"upperThreshold":10.0,
             "populationSize":3,"nominalWindowSize":7,"sampleWidth":7,"sampleHeight":7,"samplePixelCount":49,
             "classificationMethod":"FIXED_SMALL_SAMPLE","healthValidated":false}}
            """, DetectedTreeDto.class);
        var result = mapper.readTree(mapper.writeValueAsString(dto));
        assertEquals(0, result.at("/exgMetadata/value").asDouble());
        assertEquals(10, result.at("/exgMetadata/upperThreshold").asDouble());
        assertEquals(49, result.at("/exgMetadata/samplePixelCount").asInt());
        assertEquals("INTERMEDIATE", result.at("/exgMetadata/category").asText());
        assertEquals("STRESS", result.path("healthStatus").asText());
        assertEquals(31.6338, dto.lat());
        var old = mapper.readValue("{\"id\":2,\"healthStatus\":\"SAIN\"}", DetectedTreeDto.class);
        assertNull(old.exgMetadata());
        assertFalse(mapper.readTree(mapper.writeValueAsString(old)).has("exgMetadata"));
        var invalid = mapper.readValue("{\"exgMetadata\":{\"value\":null,\"category\":\"BAD\"}}", DetectedTreeDto.class);
        assertNull(invalid.exgMetadata().get("value"));
        assertEquals("BAD", invalid.exgMetadata().get("category"));
    }
}
