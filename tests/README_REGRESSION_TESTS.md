# Duplication Module Regression Tests

This document describes the comprehensive regression test suite for the Meta Ads duplication module (`meta_ads_mcp/core/duplication.py`).

## Test Coverage Overview

The regression test suite (`test_duplication_regression.py`) contains **23 comprehensive tests** organized into 7 test classes, providing extensive coverage to prevent future regressions.

### 🎯 Test Classes

#### 1. `TestDuplicationFeatureToggle` (4 tests)
- **Purpose**: Ensures the feature toggle mechanism works correctly
- **Coverage**: 
  - Feature disabled by default
  - Feature enabled with environment variable
  - Various truthy values enable the feature
  - Empty string disables the feature
- **Prevents**: Accidental feature activation, broken environment variable handling

#### 2. `TestDuplicationDecorators` (2 tests)  
- **Purpose**: Validates that all decorators are applied correctly
- **Coverage**:
  - `@meta_api_tool` decorator applied to all functions
  - `@mcp_server.tool()` decorator registers functions as MCP tools
- **Prevents**: Functions missing required decorators, broken MCP registration

#### 3. `TestDuplicationAPIContract` (3 tests)
- **Purpose**: Ensures external API calls follow the correct contract
- **Coverage**:
  - API endpoint URL construction 
  - HTTP request headers format
  - Request timeout configuration
- **Prevents**: Broken API integration, malformed requests

#### 4. `TestDuplicationErrorHandling` (3 tests)
- **Purpose**: Validates robust error handling across all scenarios
- **Coverage**:
  - Missing access token errors
  - HTTP status code handling (200, 401, 403, 429, 500)
  - Network error handling (timeouts, connection failures)
- **Prevents**: Unhandled errors, poor error messages, broken error paths

#### 5. `TestDuplicationParameterHandling` (3 tests)
- **Purpose**: Tests parameter processing and forwarding
- **Coverage**:
  - None values filtered from options
  - Parameter forwarding accuracy
  - Estimated components calculation
- **Prevents**: Malformed API requests, parameter corruption

#### 6. `TestDuplicationIntegration` (2 tests)
- **Purpose**: End-to-end functionality testing
- **Coverage**:
  - Successful duplication flow
  - Premium feature upgrade flow
- **Prevents**: Broken end-to-end flows, integration failures

#### 7. `TestDuplicationTokenHandling` (2 tests)
- **Purpose**: Access token management and injection
- **Coverage**:
  - Explicit token handling
  - Token parameter override behavior
- **Prevents**: Authentication bypasses, token handling bugs

#### 8. `TestDuplicationRegressionEdgeCases` (4 tests)
- **Purpose**: Edge cases and unusual scenarios
- **Coverage**:
  - Empty string parameters
  - Unicode parameter handling
  - Large parameter values
  - Module reload safety
- **Prevents**: Edge case failures, data corruption, memory leaks

## 🚀 Key Features Tested

### Authentication & Security
- ✅ Access token validation and injection
- ✅ Authentication error handling
- ✅ App ID validation
- ✅ Secure token forwarding

### API Integration
- ✅ HTTP client configuration
- ✅ Request/response handling
- ✅ Error status code processing
- ✅ Network failure resilience

### Feature Management
- ✅ Environment-based feature toggle
- ✅ Dynamic module loading
- ✅ MCP tool registration
- ✅ Decorator chain validation

### Data Processing
- ✅ Parameter validation and filtering
- ✅ Unicode and special character handling
- ✅ Large value processing
- ✅ JSON serialization/deserialization

### Error Resilience
- ✅ Network timeouts and failures
- ✅ Malformed responses
- ✅ Authentication failures  
- ✅ Rate limiting scenarios

## 🛡️ Regression Prevention

These tests specifically prevent the following categories of regressions:

### **Configuration Regressions**
- Feature accidentally enabled/disabled
- Environment variable handling changes
- Default configuration drift

### **Integration Regressions**
- API endpoint URL changes
- Request format modifications
- Authentication system changes

### **Error Handling Regressions**
- Silent error failures
- Poor error message quality
- Unhandled exception scenarios

### **Performance Regressions**
- Memory leaks in module reloading
- Inefficient parameter processing
- Network timeout misconfigurations

### **Security Regressions**
- Token handling vulnerabilities
- Authentication bypass bugs
- Parameter injection attacks

## 🔧 Running the Tests

```bash
# Run all regression tests
python -m pytest tests/test_duplication_regression.py -v

# Run specific test class
python -m pytest tests/test_duplication_regression.py::TestDuplicationFeatureToggle -v

# Run with coverage
python -m pytest tests/test_duplication_regression.py --cov=meta_ads_mcp.core.duplication

# Run with detailed output
python -m pytest tests/test_duplication_regression.py -vvv --tb=long
```

## 📊 Test Results

When all tests pass, you should see:
```
====================== 23 passed, 5 warnings in 0.54s ======================
```

The warnings are from mock objects and don't affect functionality.

## 🔍 Test Design Principles

1. **Isolation**: Each test is independent and can run standalone
2. **Mocking**: External dependencies are mocked for reliability
3. **Comprehensive**: Cover both happy path and error scenarios
4. **Realistic**: Use realistic data and scenarios
5. **Maintainable**: Clear test names and documentation

## 🚨 Adding New Tests

When adding new functionality to the duplication module:

1. **Add corresponding regression tests**
2. **Test both success and failure scenarios**
3. **Mock external dependencies appropriately**
4. **Use descriptive test names**
5. **Update this documentation**

## 📈 Coverage Goals

- **Line Coverage**: > 95%
- **Branch Coverage**: > 90%
- **Function Coverage**: 100%
- **Error Path Coverage**: > 85%

This comprehensive test suite ensures the duplication module remains stable and reliable across future changes and updates. 