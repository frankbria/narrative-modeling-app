/**
 * Test Data Generator for AI Recommendation Validation
 *
 * Generates 5 diverse datasets for testing AI problem type detection,
 * transformation recommendations, and algorithm suggestions.
 *
 * Run with: npx tsx generate-test-data.ts
 */

import { faker } from '@faker-js/faker';
import { writeFileSync } from 'fs';
import { join } from 'path';

const OUTPUT_DIR = join(__dirname, 'ai-test-datasets');

/**
 * Generate binary classification dataset (Customer Churn)
 * - 1000 rows, 10 columns
 * - Target: churned (0/1, 70/30 imbalance)
 * - Features: age, tenure, monthly_charges (numeric), contract_type (categorical)
 */
function generateBinaryClassification() {
  console.log('Generating binary-classification.csv...');

  const data: string[][] = [];
  data.push(['age', 'tenure', 'monthly_charges', 'contract_type', 'has_internet', 'has_phone', 'payment_method', 'total_charges', 'support_calls', 'churned']);

  for (let i = 0; i < 1000; i++) {
    const age = faker.number.int({ min: 18, max: 80 });
    const tenure = faker.number.int({ min: 0, max: 72 });
    const monthlyCharges = faker.number.float({ min: 20, max: 200, fractionDigits: 2 });
    const contractType = faker.helpers.arrayElement(['Month-to-month', 'One year', 'Two year']);
    const hasInternet = faker.datatype.boolean();
    const hasPhone = faker.datatype.boolean();
    const paymentMethod = faker.helpers.arrayElement(['Credit Card', 'Bank Transfer', 'Electronic Check', 'Mailed Check']);
    // Calculate total charges with some realistic variation (80-120% of expected total)
    const expectedTotal = monthlyCharges * Math.max(tenure, 1);
    const totalCharges = expectedTotal * (0.8 + Math.random() * 0.4);
    const supportCalls = faker.number.int({ min: 0, max: 10 });

    // Churn logic: higher churn for month-to-month contracts with low tenure
    const churnProbability = tenure < 12 && contractType === 'Month-to-month' ? 0.7 : 0.2;
    const churned = Math.random() < churnProbability ? 1 : 0;

    data.push([
      age.toString(),
      tenure.toString(),
      monthlyCharges.toFixed(2),
      contractType,
      hasInternet.toString(),
      hasPhone.toString(),
      paymentMethod,
      totalCharges.toFixed(2),
      supportCalls.toString(),
      churned.toString()
    ]);
  }

  const csv = data.map(row => row.join(',')).join('\n');
  writeFileSync(join(OUTPUT_DIR, 'binary-classification.csv'), csv);
  console.log('✅ Generated binary-classification.csv (1000 rows, 10 columns)');
}

/**
 * Generate multiclass classification dataset (Product Category)
 * - 500 rows, 8 columns
 * - Target: category (5 classes: electronics, clothing, food, books, toys)
 * - Features: price, rating, brand, color
 */
function generateMulticlassClassification() {
  console.log('Generating multiclass-classification.csv...');

  const categories = ['electronics', 'clothing', 'food', 'books', 'toys'];
  const brands = ['BrandA', 'BrandB', 'BrandC', 'BrandD', 'BrandE', 'BrandF'];
  const colors = ['red', 'blue', 'green', 'black', 'white', 'yellow', 'purple', 'orange'];

  const data: string[][] = [];
  data.push(['price', 'rating', 'brand', 'color', 'weight', 'stock_quantity', 'is_featured', 'category']);

  for (let i = 0; i < 500; i++) {
    const category = faker.helpers.arrayElement(categories);

    // Adjust price based on category
    const priceRange: Record<string, { min: number; max: number }> = {
      electronics: { min: 50, max: 1000 },
      clothing: { min: 10, max: 200 },
      food: { min: 2, max: 50 },
      books: { min: 5, max: 50 },
      toys: { min: 10, max: 100 }
    };

    const price = faker.number.float({ min: priceRange[category].min, max: priceRange[category].max, fractionDigits: 2 });
    const rating = faker.number.float({ min: 1, max: 5, fractionDigits: 1 });
    const brand = faker.helpers.arrayElement(brands);
    const color = faker.helpers.arrayElement(colors);
    const weight = faker.number.float({ min: 0.1, max: 20, fractionDigits: 2 });
    const stockQuantity = faker.number.int({ min: 0, max: 500 });
    const isFeatured = faker.datatype.boolean();

    data.push([
      price.toFixed(2),
      rating.toFixed(1),
      brand,
      color,
      weight.toFixed(2),
      stockQuantity.toString(),
      isFeatured.toString(),
      category
    ]);
  }

  const csv = data.map(row => row.join(',')).join('\n');
  writeFileSync(join(OUTPUT_DIR, 'multiclass-classification.csv'), csv);
  console.log('✅ Generated multiclass-classification.csv (500 rows, 8 columns)');
}

/**
 * Generate regression dataset (House Prices)
 * - 800 rows, 12 columns
 * - Target: price (continuous)
 * - Features: sqft, bedrooms, age, location (high cardinality)
 */
function generateRegression() {
  console.log('Generating regression.csv...');

  const locations = Array.from({ length: 50 }, (_, i) => `Location_${i + 1}`); // High cardinality

  const data: string[][] = [];
  data.push(['sqft', 'bedrooms', 'bathrooms', 'age', 'location', 'has_garage', 'has_pool', 'lot_size', 'floors', 'condition', 'school_rating', 'price']);

  for (let i = 0; i < 800; i++) {
    const sqft = faker.number.int({ min: 800, max: 4000 });
    const bedrooms = faker.number.int({ min: 1, max: 6 });
    const bathrooms = faker.number.int({ min: 1, max: 4 });
    const age = faker.number.int({ min: 0, max: 100 });
    const location = faker.helpers.arrayElement(locations);
    const hasGarage = faker.datatype.boolean();
    const hasPool = faker.datatype.boolean();
    const lotSize = faker.number.int({ min: 2000, max: 20000 });
    const floors = faker.number.int({ min: 1, max: 3 });
    const condition = faker.number.int({ min: 1, max: 5 });
    const schoolRating = faker.number.int({ min: 1, max: 10 });

    // Price formula: base price from sqft + adjustments
    const basePrice = sqft * 150;
    const bedroomBonus = bedrooms * 20000;
    const ageDiscount = age * 1000;
    const garageBonus = hasGarage ? 50000 : 0;
    const poolBonus = hasPool ? 75000 : 0;
    const conditionBonus = condition * 30000;
    const schoolBonus = schoolRating * 10000;

    const price = basePrice + bedroomBonus - ageDiscount + garageBonus + poolBonus + conditionBonus + schoolBonus;

    data.push([
      sqft.toString(),
      bedrooms.toString(),
      bathrooms.toString(),
      age.toString(),
      location,
      hasGarage.toString(),
      hasPool.toString(),
      lotSize.toString(),
      floors.toString(),
      condition.toString(),
      schoolRating.toString(),
      Math.round(price).toString()
    ]);
  }

  const csv = data.map(row => row.join(',')).join('\n');
  writeFileSync(join(OUTPUT_DIR, 'regression.csv'), csv);
  console.log('✅ Generated regression.csv (800 rows, 12 columns)');
}

/**
 * Generate time series dataset (Sales Forecast)
 * - 365 rows (daily data for 1 year)
 * - Columns: date, sales, temperature, holiday (binary)
 * - Seasonal patterns present
 */
function generateTimeSeries() {
  console.log('Generating timeseries.csv...');

  const data: string[][] = [];
  data.push(['date', 'sales', 'temperature', 'is_holiday', 'day_of_week', 'month']);

  const startDate = new Date('2024-01-01');

  for (let i = 0; i < 365; i++) {
    const currentDate = new Date(startDate);
    currentDate.setDate(startDate.getDate() + i);

    const dateStr = currentDate.toISOString().split('T')[0];
    const dayOfWeek = currentDate.getDay(); // 0 = Sunday, 6 = Saturday
    const month = currentDate.getMonth() + 1; // 1-12

    // Seasonal pattern: higher sales in Nov-Dec (holidays)
    const seasonalFactor = month >= 11 ? 1.5 : 1.0;

    // Weekly pattern: higher sales on weekends
    const weekendFactor = (dayOfWeek === 0 || dayOfWeek === 6) ? 1.3 : 1.0;

    // Holiday effect
    const isHoliday = faker.datatype.boolean({ probability: 0.05 }); // ~5% of days
    const holidayFactor = isHoliday ? 1.8 : 1.0;

    // Temperature effect (higher in summer)
    const temperature = 50 + 20 * Math.sin((month - 1) * Math.PI / 6) + faker.number.int({ min: -10, max: 10 });
    const tempFactor = temperature > 70 ? 1.2 : 0.9;

    // Base sales with all factors
    const baseSales = 1000;
    const sales = Math.round(baseSales * seasonalFactor * weekendFactor * holidayFactor * tempFactor * (0.8 + Math.random() * 0.4));

    data.push([
      dateStr,
      sales.toString(),
      temperature.toFixed(1),
      isHoliday.toString(),
      dayOfWeek.toString(),
      month.toString()
    ]);
  }

  const csv = data.map(row => row.join(',')).join('\n');
  writeFileSync(join(OUTPUT_DIR, 'timeseries.csv'), csv);
  console.log('✅ Generated timeseries.csv (365 rows, 6 columns)');
}

/**
 * Generate clustering dataset (Customer Segmentation)
 * - 600 rows, 6 columns
 * - No target column (unsupervised)
 * - Features: age, income, purchase_frequency, avg_order_value
 */
function generateClustering() {
  console.log('Generating clustering.csv...');

  const data: string[][] = [];
  data.push(['age', 'income', 'purchase_frequency', 'avg_order_value', 'customer_lifetime_value', 'satisfaction_score']);

  // Create 3 clusters with different characteristics
  const clusters = [
    { // Budget-conscious, younger
      ageRange: { min: 18, max: 35 },
      incomeRange: { min: 20000, max: 50000 },
      frequencyRange: { min: 1, max: 5 },
      orderValueRange: { min: 20, max: 100 }
    },
    { // Mid-tier, middle-aged
      ageRange: { min: 35, max: 55 },
      incomeRange: { min: 50000, max: 100000 },
      frequencyRange: { min: 5, max: 15 },
      orderValueRange: { min: 100, max: 300 }
    },
    { // Premium, older
      ageRange: { min: 45, max: 75 },
      incomeRange: { min: 80000, max: 200000 },
      frequencyRange: { min: 10, max: 30 },
      orderValueRange: { min: 200, max: 1000 }
    }
  ];

  for (let i = 0; i < 600; i++) {
    const cluster = faker.helpers.arrayElement(clusters);

    const age = faker.number.int({ min: cluster.ageRange.min, max: cluster.ageRange.max });
    const income = faker.number.int({ min: cluster.incomeRange.min, max: cluster.incomeRange.max });
    const purchaseFrequency = faker.number.int({ min: cluster.frequencyRange.min, max: cluster.frequencyRange.max });
    const avgOrderValue = faker.number.float({ min: cluster.orderValueRange.min, max: cluster.orderValueRange.max, fractionDigits: 2 });
    const customerLifetimeValue = purchaseFrequency * avgOrderValue;
    const satisfactionScore = faker.number.float({ min: 1, max: 5, fractionDigits: 1 });

    data.push([
      age.toString(),
      income.toString(),
      purchaseFrequency.toString(),
      avgOrderValue.toFixed(2),
      customerLifetimeValue.toFixed(2),
      satisfactionScore.toFixed(1)
    ]);
  }

  const csv = data.map(row => row.join(',')).join('\n');
  writeFileSync(join(OUTPUT_DIR, 'clustering.csv'), csv);
  console.log('✅ Generated clustering.csv (600 rows, 6 columns)');
}

/**
 * Generate additional standard test datasets
 */
function generateStandardDatasets() {
  console.log('\nGenerating standard test datasets...');

  // 1. diverse-types.csv - Schema inference testing
  console.log('Generating diverse-types.csv...');
  const diverseData: string[][] = [];
  diverseData.push(['id', 'name', 'age', 'price', 'is_active', 'created_at', 'category', 'tags']);

  for (let i = 0; i < 100; i++) {
    diverseData.push([
      i.toString(),
      faker.person.fullName(),
      faker.number.int({ min: 18, max: 80 }).toString(),
      faker.number.float({ min: 10, max: 1000, fractionDigits: 2 }).toString(),
      faker.datatype.boolean().toString(),
      faker.date.past().toISOString(),
      faker.helpers.arrayElement(['A', 'B', 'C', 'D', 'E']),
      faker.helpers.arrayElements(['tag1', 'tag2', 'tag3', 'tag4'], { min: 1, max: 3 }).join(';')
    ]);
  }
  writeFileSync(join(__dirname, 'diverse-types.csv'), diverseData.map(row => row.join(',')).join('\n'));
  console.log('✅ Generated diverse-types.csv (100 rows, 8 types)');

  // 2. missing-values.csv - Imputation testing
  console.log('Generating missing-values.csv...');
  const missingData: string[][] = [];
  missingData.push(['col1', 'col2', 'col3', 'col4', 'col5', 'col6']);

  for (let i = 0; i < 200; i++) {
    missingData.push([
      Math.random() < 0.3 ? '' : faker.number.int({ min: 1, max: 100 }).toString(),
      Math.random() < 0.3 ? '' : faker.number.float({ min: 0, max: 1, fractionDigits: 3 }).toString(),
      Math.random() < 0.3 ? '' : faker.person.firstName(),
      Math.random() < 0.3 ? '' : faker.helpers.arrayElement(['A', 'B', 'C']),
      Math.random() < 0.3 ? '' : faker.datatype.boolean().toString(),
      Math.random() < 0.3 ? '' : faker.date.past().toISOString()
    ]);
  }
  writeFileSync(join(__dirname, 'missing-values.csv'), missingData.map(row => row.join(',')).join('\n'));
  console.log('✅ Generated missing-values.csv (200 rows, 30% missing)');

  // 3. large-dataset.csv - Performance testing
  console.log('Generating large-dataset.csv...');
  const largeData: string[][] = [];
  largeData.push(['id', 'field1', 'field2', 'field3', 'field4', 'field5', 'field6', 'field7', 'field8', 'field9', 'field10', 'field11', 'field12', 'field13', 'field14', 'field15']);

  for (let i = 0; i < 10000; i++) {
    largeData.push([
      i.toString(),
      faker.number.int({ min: 1, max: 1000 }).toString(),
      faker.number.float({ min: 0, max: 100, fractionDigits: 2 }).toString(),
      faker.person.firstName(),
      faker.person.lastName(),
      faker.internet.email(),
      faker.phone.number(),
      faker.location.city(),
      faker.location.state(),
      faker.location.zipCode(),
      faker.date.past().toISOString().split('T')[0],
      faker.helpers.arrayElement(['Active', 'Inactive', 'Pending']),
      faker.datatype.boolean().toString(),
      faker.number.int({ min: 0, max: 10 }).toString(),
      faker.number.float({ min: 0, max: 1000, fractionDigits: 2 }).toString(),
      faker.lorem.sentence()
    ]);
  }
  writeFileSync(join(__dirname, 'large-dataset.csv'), largeData.map(row => row.join(',')).join('\n'));
  console.log('✅ Generated large-dataset.csv (10,000 rows, 15 columns)');
}

/**
 * Main execution
 */
function main() {
  console.log('=== Test Data Generator ===\n');
  console.log(`Output directory: ${OUTPUT_DIR}\n`);

  try {
    // Generate AI test datasets
    console.log('--- AI Test Datasets ---');
    generateBinaryClassification();
    generateMulticlassClassification();
    generateRegression();
    generateTimeSeries();
    generateClustering();

    // Generate standard test datasets
    generateStandardDatasets();

    console.log('\n✅ All test datasets generated successfully!');
    console.log('\nNext steps:');
    console.log('1. Run the E2E tests: npm run test:e2e');
    console.log('2. Implement AI mocking if needed for CI/CD');
  } catch (error) {
    console.error('\n❌ Error generating test data:', error);
    process.exit(1);
  }
}

main();
