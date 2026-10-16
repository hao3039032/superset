/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
import {
  customEChartOptionsSchema,
  legendSchema,
  validateEChartOptions,
} from './eChartOptionsSchema';

// =============================================================================
// legend.selected
// =============================================================================

test('legendSchema accepts a selected map of series names to booleans', () => {
  const result = legendSchema.safeParse({
    selected: { 'Series A': false, 'Series B': true },
  });

  expect(result.success).toBe(true);
  if (result.success) {
    expect(result.data.selected).toEqual({
      'Series A': false,
      'Series B': true,
    });
  }
});

test('legendSchema accepts an empty selected map', () => {
  const result = legendSchema.safeParse({ selected: {} });

  expect(result.success).toBe(true);
});

test('legendSchema rejects a selected map with non-boolean values', () => {
  const result = legendSchema.safeParse({
    selected: { 'Series A': 'false' },
  });

  expect(result.success).toBe(false);
});

test('legendSchema rejects a non-object selected value', () => {
  const result = legendSchema.safeParse({
    selected: ['Series A', 'Series B'],
  });

  expect(result.success).toBe(false);
});

test('legend.selected is optional', () => {
  const result = legendSchema.safeParse({ show: true });

  expect(result.success).toBe(true);
  if (result.success) {
    expect(result.data.selected).toBeUndefined();
  }
});

// =============================================================================
// Full options validation
// =============================================================================

test('customEChartOptionsSchema validates legend.selected within full options', () => {
  const result = customEChartOptionsSchema.safeParse({
    legend: { selected: { 'Series A': false } },
  });

  expect(result.success).toBe(true);
  if (result.success) {
    expect(result.data.legend).toMatchObject({
      selected: { 'Series A': false },
    });
  }
});

test('validateEChartOptions rejects invalid legend.selected values', () => {
  const result = validateEChartOptions({
    legend: { selected: { 'Series A': 0 } },
  });

  expect(result.success).toBe(false);
});

test('customEChartOptionsSchema accepts a legend array with selected maps', () => {
  const result = customEChartOptionsSchema.safeParse({
    legend: [{ selected: { 'Series A': false } }, { show: false }],
  });

  expect(result.success).toBe(true);
});
