# Transformation Preview System - User Guide

## Overview

The transformation preview system allows you to see the effects of data transformations before applying them permanently. This helps you:
- Verify transformations work as expected
- Understand impact on data quality
- Identify potential issues before committing changes
- Make informed decisions about transformation choices

## How to Use the Preview System

### Step 1: Configure Transformations

Add transformation operations to your pipeline:
1. Navigate to your dataset's transformation page
2. Click "Add Transformation"
3. Select transformation type (e.g., "Remove Nulls", "Remove Outliers")
4. Choose the column to transform
5. Configure parameters (if applicable)

### Step 2: View Real-Time Preview

As you add transformations, the preview automatically updates:
- **Before/After View**: Side-by-side comparison of original vs transformed data
- **Impact Statistics**: Metrics showing how transformations affect your data
- **Quality Score**: Data quality before and after transformations

### Step 3: Adjust Sample Size

Control how many rows to preview:
- Default: 100 rows
- Minimum: 10 rows (faster, less detail)
- Maximum: 1000 rows (slower, more detail)

**Recommendation**: Use 100 rows for quick previews, 500-1000 for final validation.

### Step 4: Interpret Impact Statistics

The preview shows four key metrics:

#### 1. Rows Affected
Number of rows with ANY changes
- Example: "45 rows" means 45 rows have at least one cell modified
- Important for understanding scope of transformation

#### 2. Values Changed
Total number of cells modified
- Example: "127 cells" means 127 individual cell values were changed
- Helps identify unexpected transformations (too many changes = possible error)

#### 3. Columns Affected
Which columns have changes
- Example: "age, salary" means only these columns were modified
- Verify that transformations only affect intended columns

#### 4. Quality Score
Data quality before and after (0% to 100%)
- **0.0-0.3**: Poor quality (many nulls, outliers, inconsistencies)
- **0.4-0.6**: Fair quality (some issues present)
- **0.7-0.8**: Good quality (minimal issues)
- **0.9-1.0**: Excellent quality (very few or no issues)

The quality score improves when:
- Null values are replaced with meaningful data
- Outliers are removed
- Data consistency is improved
- Duplicates are eliminated

### Step 5: Review Warnings

Yellow warning boxes appear if:
- Transformation replaced null values
- Outliers were removed
- Data types were coerced
- Edge cases were encountered

**Always review warnings** before applying transformations. They indicate what changed and why.

Example warnings:
- "Replaced 5 null values in 'age' column with mean (28.5)"
- "Removed 3 outliers in 'salary' column (IQR method)"
- "Coerced 10 values in 'date' column to valid date format"

### Step 6: Compare Before/After Data

Use the side-by-side comparison to:
- Verify transformations applied correctly
- Check for unexpected changes
- Validate data quality improvements

**Yellow highlighted cells** indicate changed values. Hover to see:
- Old value (original)
- New value (transformed)

Example:
```
Original: age = null  →  Transformed: age = 28
Original: salary = 250000  →  Transformed: salary = 95000 (outlier removed)
```

### Step 7: Apply or Discard

Once satisfied with the preview:
- **Apply Transformations**: Click "Apply" to commit changes to dataset
- **Adjust & Preview Again**: Modify transformation settings and regenerate preview
- **Cancel**: Discard without applying

## Best Practices

### Sample Size Selection

| Use Case | Recommended Size | Reason |
|----------|------------------|--------|
| Quick check | 10-50 rows | Fast (200-500ms), sufficient for obvious issues |
| Normal validation | 100 rows (default) | Balanced speed (500ms-1s) and detail |
| Final verification | 500-1000 rows | Comprehensive (1-3s), catches edge cases |
| Small dataset (<1000 rows) | 100% of data | Can safely preview entire dataset |

### Understanding Quality Scores

Quality score is calculated based on:
1. **Null/missing values** (major factor)
   - More nulls = lower score
   - Nulls replaced = significant improvement

2. **Outliers** (medium factor)
   - Statistical anomalies = lower score
   - Outliers removed = quality improvement

3. **Data consistency** (medium factor)
   - Inconsistent formats = lower score
   - Standardization = quality improvement

4. **Duplicates** (medium factor)
   - More duplicates = lower score
   - Duplicates removed = quality improvement

5. **Data types** (minor factor)
   - Mismatched types = slightly lower score
   - Correct types = slightly higher score

Example quality score trajectory:
- Raw data: 0.65 (some missing values, outliers)
- Remove nulls: 0.78 (significant improvement)
- Remove outliers: 0.85 (additional improvement)
- Remove duplicates: 0.92 (nearly perfect)

### Transformation Order Matters

Transformations are applied sequentially, so order affects results.

**Example**: Different results from same operations in different order

Order 1: Remove Nulls → Remove Outliers
```
Original: [10, 20, null, 1000, 30]
Step 1 (Remove Nulls): [10, 20, 1000, 30]
Step 2 (Remove Outliers): [10, 20, 30]  ← 1000 removed as outlier
Result: 3 values
```

Order 2: Remove Outliers → Remove Nulls
```
Original: [10, 20, null, 1000, 30]
Step 1 (Remove Outliers): [10, 20, null, 30]  ← 1000 removed as outlier
Step 2 (Remove Nulls): [10, 20, 30]
Result: 3 values (same in this case)
```

**Best Practice**: Order transformations logically:
1. Remove duplicates (clean data first)
2. Remove nulls (handle missing values)
3. Remove outliers (clean remaining anomalies)
4. Standardize (format consistency)
5. Encode categorical (prepare for modeling)

## Troubleshooting

### Preview Takes Too Long (>5 seconds)

**Causes**:
- Sample size too large (>500 rows)
- Complex transformations (multiple sequential operations)
- Large dataset file (slow S3 load)

**Solutions**:
- Reduce sample size to 100 rows for quick checks
- Break transformations into smaller batches
- Wait for caching to activate (subsequent previews are faster)
- Check network connection

**Performance by sample size**:
- 10 rows: ~200-500ms
- 100 rows: ~500ms-1s (recommended default)
- 500 rows: ~1-2s
- 1000 rows: ~2-3s

### Preview Shows Unexpected Changes

**Causes**:
- Transformation order matters (operations are sequential)
- Parameters misconfigured
- Edge cases in data
- Transformation applied to wrong column

**Solutions**:
- Review transformation order (reorder if needed)
- Check transformation parameters
- Increase sample size to catch edge cases
- Verify column selection
- Regenerate preview to confirm

### "Preview Generation Timeout" Error

**Causes**:
- Sample size >500 rows with complex transformations
- Dataset file is very large (slow S3 load)
- Server under heavy load

**Solutions**:
- Reduce sample size to 100 rows
- Simplify transformation operations
- Remove unnecessary transformations
- Try again in a few minutes if server load is high

**Note**: If timeouts persist, contact support with dataset ID and transformation details.

### "Rate Limit Exceeded" or "Too Many Requests" Error

**Causes**:
- Making >10 preview requests per minute
- Too many rapid changes to transformations
- Multiple browser tabs making concurrent requests

**Solutions**:
- Slow down editing (wait 1-2 seconds between changes)
- Close duplicate browser tabs
- Debouncing automatically reduces requests (300ms delay)
- Batch multiple changes before previewing

**Note**: Rate limiting protects server resources. Brief waits (30 seconds) usually resolve this.

### "Dataset Not Found" Error

**Causes**:
- Dataset was deleted
- Wrong dataset ID
- Insufficient permissions
- Network error

**Solutions**:
- Verify dataset exists in your dataset list
- Refresh page and try again
- Check that you're logged in with correct account
- Contact support if problem persists

### Preview Works but Warnings Appear

This is normal and not an error. Warnings indicate what was changed.

**Common warnings**:
- "Replaced 5 null values" → Normal for missing data
- "Removed 2 outliers" → Expected for outlier removal
- "Coerced values to date format" → Expected for type conversion

**What to do**:
- Review warnings to understand changes
- Verify changes are acceptable
- Apply transformation if satisfied
- Adjust parameters if not satisfied

## Advanced Features

### Value Distribution Changes

Expand "Value Distribution Changes" to see:
- Before/after value counts
- Frequency changes
- New values introduced
- Values removed

Use this to:
- Verify null replacements worked correctly
  - Before: `null: 5`
  - After: `null: 0, mean_value: 5` (properly replaced)
- Check outlier removal accuracy
  - Before: `95000: 1, 100000: 2`
  - After: Only normal values remain
- Validate categorical encoding
  - Before: `A: 100, B: 50, C: 10`
  - After: `cat_0: 100, cat_1: 50, cat_2: 10` (properly encoded)

### Export Preview

Click "Export" button to download preview as CSV file:
- Includes both original and transformed columns
- Useful for offline analysis
- Limited to sample size selected
- Format: `dataset_id_preview_YYYY-MM-DD.csv`

Use exported files for:
- Offline analysis in Excel
- Sharing with team members
- Documentation
- Before/after comparison

### Value Distribution Analysis

When expanding value distribution details, you see frequency tables:

**Before transformation**:
```
age:
  null: 45 occurrences
  25: 30 occurrences
  30: 15 occurrences
  45: 10 occurrences
```

**After transformation**:
```
age:
  28: 45 occurrences (null replaced with mean)
  25: 30 occurrences (unchanged)
  30: 15 occurrences (unchanged)
  45: 10 occurrences (unchanged)
```

This helps verify:
- All nulls were replaced
- Original values were preserved
- Replacement values are reasonable

## Performance Tips

### Faster Previews

1. **Use caching** (when implemented)
   - Identical transformations use cached results (5 minute TTL)
   - Cache automatically activated for repeated operations

2. **Start small**
   - Preview with 10-50 rows first
   - Increase to 100-500 for final validation
   - Use maximum sample only for final checks

3. **Batch edits**
   - Make multiple changes before previewing
   - Wait 300ms (debounce delay) before next preview
   - Reduces redundant API calls

4. **Simplify transformations**
   - Break complex operations into steps
   - Preview each step separately
   - Helps identify slow operations

### Memory Optimization

Preview system is optimized for memory efficiency:
- Loads only sample_size rows from file (not entire file)
- Maximum memory: ~200 MB for 1000 rows
- Safe for datasets up to 100GB

Example memory usage:
- 1 GB CSV file (1M rows) → Sample 100 rows → Uses ~30 MB
- 10 GB CSV file (10M rows) → Sample 1000 rows → Uses ~200 MB

## Privacy & Security

- Previews are user-scoped (you only see your data)
- Cache keys include user ID (no cross-user leakage)
- Previews expire after 5 minutes (no long-term storage)
- Ownership verified before generating preview
- All data stays within secure infrastructure

## Common Transformation Examples

### Example 1: Handle Missing Age Data

**Scenario**: Age column has 45 null values, need to estimate

**Steps**:
1. Add transformation: "Fill Missing" on age column
2. Method: "mean"
3. Click preview
4. Review: 45 rows affected, quality improves from 0.72 to 0.81
5. Check warnings: "Replaced 45 null values with mean (28.5)"
6. Apply transformation

**Result**: All age nulls replaced with mean value, data quality improves

### Example 2: Remove Salary Outliers

**Scenario**: Salary has extreme outliers (CEO salary), want to remove

**Steps**:
1. Add transformation: "Remove Outliers" on salary column
2. Method: "IQR"
3. Click preview
4. Review: 3 rows affected, quality improves from 0.78 to 0.84
5. Check warnings: "Removed 3 outlier values"
6. Click "Value Distribution Changes" to see removed values
7. Apply transformation

**Result**: Extreme salary values removed, distribution normalized

### Example 3: Standardize Date Format

**Scenario**: Date column has inconsistent formats (MM/DD/YYYY and DD-MM-YYYY)

**Steps**:
1. Add transformation: "Standardize" on date column
2. Format: "YYYY-MM-DD"
3. Click preview
4. Review: 15 rows affected (inconsistently formatted ones)
5. Check warnings: "Coerced 15 values to date format"
6. Apply transformation

**Result**: All dates in consistent format

### Example 4: Remove Duplicate Rows

**Scenario**: Dataset has duplicate entries

**Steps**:
1. Add transformation: "Remove Duplicates"
2. (No column selection needed - compares entire row)
3. Click preview
4. Review: Shows number of duplicate rows found
5. Check warnings: "Removed X duplicate rows"
6. Apply transformation

**Result**: No duplicate rows remain

## Getting Help

If you encounter issues:

1. **Check this guide** for troubleshooting tips
2. **Review warning messages** in preview (they explain what changed)
3. **Verify transformation parameters** are correct
4. **Try with smaller sample size** (100 rows) first
5. **Check internet connection** if timeouts occur

When contacting support, provide:
- Dataset ID (from URL or dataset list)
- Transformation operations being applied
- Error message (if any)
- Sample size used
- Screenshot of preview (if relevant)

## FAQ

**Q: Why did the quality score go down after my transformation?**
A: Some transformations may temporarily decrease quality. For example, removing outliers removes extreme values but might reduce statistical diversity. Review the transformation to ensure it aligns with your goals.

**Q: Can I preview without applying?**
A: Yes! Preview is designed for exactly this purpose. You can preview as many times as needed. Only click "Apply" when satisfied.

**Q: What happens if I make a mistake when applying?**
A: You can revert by reloading your dataset (if not saved) or applying a reverse transformation. Always review preview carefully before applying.

**Q: Is the preview always accurate?**
A: The preview is based on a sample, so edge cases might not appear in small samples. Use larger sample sizes (500-1000 rows) for final validation.

**Q: How long do previews take?**
A: 100 rows: ~500ms-1s, 500 rows: ~1-2s, 1000 rows: ~2-3s. Depends on transformation complexity.

**Q: Can I share previews with colleagues?**
A: Export the preview as CSV and share the file. Colleagues can see before/after data without access to your account.

**Q: What if my dataset is very large (>1GB)?**
A: Use 100-500 row samples for preview. The system loads only the sample from disk (not entire file), so it's memory efficient even for huge datasets.

---

## See Also

- **API Documentation**: `/api/docs` (OpenAPI/Swagger specification)
- **Performance Guide**: `PREVIEW_PERFORMANCE.md` (technical details)
- **Backend Implementation**: `apps/backend/app/services/data_processing/preview_service.py`
- **Frontend Component**: `apps/frontend/components/transformation/TransformationPreview.tsx`

---

*Last Updated: 2025-12-19*
