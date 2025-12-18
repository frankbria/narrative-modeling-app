# useDebounce Hook

## Overview

A custom React hook that debounces a value for a specified delay. This is useful for optimizing performance when dealing with frequently-changing values like search inputs, form fields, or filter parameters.

## Signature

```typescript
export function useDebounce<T>(value: T, delay: number = 300): T
```

## Parameters

- `value: T` - The value to debounce. Can be any type (string, number, object, etc.)
- `delay: number` - The debounce delay in milliseconds. Defaults to 300ms.

## Returns

- `T` - The debounced value. Updates only after `delay` milliseconds of inactivity.

## Usage Example

### Basic Search Example

```tsx
import { useDebounce } from '@/lib/hooks/useDebounce';

export function SearchComponent() {
  const [searchTerm, setSearchTerm] = useState('');
  const debouncedSearchTerm = useDebounce(searchTerm, 300);

  useEffect(() => {
    // This effect only runs when debouncedSearchTerm changes
    // i.e., 300ms after the user stops typing
    console.log('Searching for:', debouncedSearchTerm);
    fetchSearchResults(debouncedSearchTerm);
  }, [debouncedSearchTerm]);

  return (
    <input
      value={searchTerm}
      onChange={(e) => setSearchTerm(e.target.value)}
      placeholder="Search..."
    />
  );
}
```

### API Request with Debounce

```tsx
const [filters, setFilters] = useState({ query: '', category: '' });
const debouncedFilters = useDebounce(filters, 500);

useEffect(() => {
  // Only makes API call 500ms after last filter change
  api.getFilteredData(debouncedFilters).then(setResults);
}, [debouncedFilters]);
```

### Form Auto-save Example

```tsx
const [formData, setFormData] = useState(initialData);
const debouncedFormData = useDebounce(formData, 2000);

useEffect(() => {
  // Auto-save 2 seconds after user stops typing
  api.saveFormData(debouncedFormData);
}, [debouncedFormData]);
```

## How It Works

The hook uses `setTimeout` to delay updating the returned value:

1. When `value` changes, a timer is started for `delay` milliseconds
2. If `value` changes again before the timer completes, the previous timer is cancelled and a new one is started
3. After `delay` milliseconds without changes, the `debouncedValue` updates to the current `value`
4. The hook cleans up the timer when the component unmounts or when dependencies change

## Performance Benefits

### Reduced API Calls
- Without debounce: 1 API call per keystroke (e.g., 10+ calls for "javascript")
- With debounce: 1 API call after user stops typing

### Example with 200+ chars search:
```
Time:     0ms    100ms   200ms   300ms   400ms   500ms
Without:  [API]  [API]   [API]   [API]   [API]   [API]  = 6 calls
With 300ms debounce:
Input:    [t]    [te]    [tes]   [test]  (wait)  [API]   = 1 call
```

### Reduced Server Load
- Fewer API requests means less server processing
- Better for rate-limited APIs
- Reduces bandwidth usage

### Improved User Experience
- Smoother search/filter experience
- No lag from excessive processing
- More responsive UI

## Common Use Cases

1. **Search inputs** - Wait for user to finish typing before searching
2. **Filter controls** - Delay applying filters until user is done adjusting
3. **Form inputs** - Debounce validation or auto-save
4. **Window resize handlers** - Debounce layout calculations
5. **Mouse move tracking** - Reduce event handling frequency
6. **Analytics events** - Batch similar events together

## Comparison with Other Approaches

### Without Debounce (Immediate)
```tsx
useEffect(() => {
  console.log('Search:', searchTerm);
}, [searchTerm]); // Runs on every keystroke
```
- Pros: Real-time responsiveness
- Cons: Excessive processing, API calls, server load

### With Debounce
```tsx
const debouncedTerm = useDebounce(searchTerm, 300);
useEffect(() => {
  console.log('Search:', debouncedTerm);
}, [debouncedTerm]); // Runs 300ms after typing stops
```
- Pros: Reduced processing, better performance
- Cons: Slight delay in UI updates

### Throttle (Different Approach)
```tsx
// Executes at most once per interval
setInterval(() => {
  processValue(searchTerm); // Runs every 300ms
}, 300);
```
- Pros: Predictable execution timing
- Cons: May lose final value

## Customization

### Custom Delay Values

```tsx
// Short delay for fast typing
const fast = useDebounce(value, 100);

// Medium delay (default)
const medium = useDebounce(value);

// Long delay for expensive operations
const slow = useDebounce(value, 1000);
```

### With Complex Types

```tsx
interface FilterOptions {
  query: string;
  category: string;
  sortBy: 'date' | 'relevance';
}

const filters: FilterOptions = { query: '', category: '', sortBy: 'date' };
const debouncedFilters = useDebounce(filters, 300);
```

## Testing

When testing components that use `useDebounce`:

```typescript
import { useDebounce } from '@/lib/hooks/useDebounce';

jest.useFakeTimers();

test('debounce delays value update', () => {
  const { result, rerender } = renderHook(
    ({ value }) => useDebounce(value, 300),
    { initialProps: { value: 'initial' } }
  );

  expect(result.current).toBe('initial');

  rerender({ value: 'updated' });
  expect(result.current).toBe('initial'); // Still the old value

  jest.advanceTimersByTime(300);
  expect(result.current).toBe('updated'); // Now updated
});

jest.useRealTimers();
```

## Best Practices

1. **Choose appropriate delay values**
   - Search: 200-500ms
   - Form validation: 500-1000ms
   - Auto-save: 1000-2000ms
   - Heavy computation: 500-1000ms

2. **Combine with loading states**
   ```tsx
   const [isSearching, setIsSearching] = useState(false);
   const debouncedTerm = useDebounce(searchTerm, 300);

   useEffect(() => {
     setIsSearching(true);
     fetchResults(debouncedTerm).then(() => setIsSearching(false));
   }, [debouncedTerm]);
   ```

3. **Don't overuse debouncing**
   - Use debounce only for expensive operations
   - For simple state updates, immediate updates are better

4. **Consider race conditions**
   - If multiple debounced values affect the same effect, coordinate them
   - Use unique dependencies for each effect

5. **Clean up properly**
   - The hook automatically cleans up timers
   - Ensure effects clean up properly when debounced values change

## Related Hooks

- `useThrottle` - Execute at most once per interval (doesn't exist in this codebase yet)
- `useDebounceCallback` - Debounced function execution
- `usePrevious` - Access previous value for comparison

## Browser Support

- All modern browsers support `setTimeout` and `useEffect`
- IE 11+ supported
- No special polyfills required
