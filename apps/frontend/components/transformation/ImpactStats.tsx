"use client";

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, TrendingUp, TrendingDown } from "lucide-react";

interface ImpactStatistics {
  rows_affected: number;
  values_changed: number;
  columns_affected: string[];
  quality_score_before: number;
  quality_score_after: number;
  value_distributions?: Record<
    string,
    { before: Record<string, number>; after: Record<string, number> }
  >;
}

export interface ImpactStatsProps {
  impactStats: ImpactStatistics;
}

/**
 * ImpactStats Dashboard Component
 *
 * Displays transformation impact metrics including:
 * - Rows affected and values changed
 * - Columns affected list
 * - Quality score comparison with visual progress bars
 * - Optional value distribution changes
 *
 * Features color-coded quality improvements/degradations and expandable
 * distribution details for detailed analysis.
 */
export function ImpactStats({ impactStats }: ImpactStatsProps) {
  const [expandedDistributions, setExpandedDistributions] = useState(false);

  // Calculate quality score change
  const qualityChange =
    impactStats.quality_score_after - impactStats.quality_score_before;
  const qualityChangePercent = (Math.abs(qualityChange) * 100).toFixed(1);
  const qualityImproved = qualityChange > 0;
  const qualityDegraded = qualityChange < 0;

  // Format percentage display
  const beforePercent = (impactStats.quality_score_before * 100).toFixed(0);
  const afterPercent = (impactStats.quality_score_after * 100).toFixed(0);

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-foreground">Impact Statistics</h3>

      {/* Metrics Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Rows Affected */}
        <Card className="bg-card">
          <CardContent className="pt-6">
            <div className="text-sm font-medium text-muted-foreground">
              Rows Affected
            </div>
            <div className="mt-2 text-3xl font-bold text-foreground">
              {impactStats.rows_affected.toLocaleString()}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">rows with changes</div>
          </CardContent>
        </Card>

        {/* Values Changed */}
        <Card className="bg-card">
          <CardContent className="pt-6">
            <div className="text-sm font-medium text-muted-foreground">
              Values Changed
            </div>
            <div className="mt-2 text-3xl font-bold text-foreground">
              {impactStats.values_changed.toLocaleString()}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">cells modified</div>
          </CardContent>
        </Card>

        {/* Columns Affected */}
        <Card className="bg-card">
          <CardContent className="pt-6">
            <div className="text-sm font-medium text-muted-foreground">
              Columns Affected
            </div>
            <div className="mt-2 text-3xl font-bold text-foreground">
              {impactStats.columns_affected.length}
            </div>
            <div className="mt-1 text-xs text-muted-foreground truncate">
              {impactStats.columns_affected.length > 0
                ? impactStats.columns_affected.join(", ")
                : "none"}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quality Score Comparison */}
      <Card className="bg-card">
        <CardHeader>
          <CardTitle className="text-base">Quality Score Comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Score Labels */}
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">Before</span>
              <span className="text-sm font-medium text-foreground">After</span>
            </div>

            {/* Score Bars */}
            <div className="flex items-center gap-3">
              {/* Before Score */}
              <div className="flex-1 space-y-1">
                <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-blue-500 h-3 transition-all duration-500 flex items-center justify-center"
                    style={{
                      width: `${impactStats.quality_score_before * 100}%`,
                    }}
                  />
                </div>
                <div className="text-xs font-semibold text-foreground">
                  {beforePercent}%
                </div>
              </div>

              {/* Arrow Indicator */}
              <div className="flex-shrink-0 flex justify-center">
                {qualityImproved ? (
                  <TrendingUp className="w-5 h-5 text-green-600" />
                ) : qualityDegraded ? (
                  <TrendingDown className="w-5 h-5 text-red-600" />
                ) : (
                  <div className="w-5 h-5 text-gray-400 flex items-center justify-center">
                    →
                  </div>
                )}
              </div>

              {/* After Score */}
              <div className="flex-1 space-y-1">
                <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                  <div
                    className={`h-3 transition-all duration-500 ${
                      qualityImproved
                        ? "bg-green-500"
                        : qualityDegraded
                          ? "bg-red-500"
                          : "bg-blue-500"
                    }`}
                    style={{
                      width: `${impactStats.quality_score_after * 100}%`,
                    }}
                  />
                </div>
                <div className="text-xs font-semibold text-foreground">
                  {afterPercent}%
                </div>
              </div>
            </div>

            {/* Quality Change Badge */}
            {qualityChange !== 0 && (
              <div className="flex justify-center mt-2">
                <Badge
                  variant={qualityImproved ? "default" : "secondary"}
                  className={
                    qualityImproved
                      ? "bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200 hover:bg-green-100"
                      : "bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200 hover:bg-red-100"
                  }
                >
                  {qualityImproved ? (
                    <TrendingUp className="w-3 h-3 mr-1" />
                  ) : (
                    <TrendingDown className="w-3 h-3 mr-1" />
                  )}
                  {qualityChangePercent}% {qualityImproved ? "improvement" : "degradation"}
                </Badge>
              </div>
            )}

            {/* No Change Message */}
            {qualityChange === 0 && (
              <div className="flex justify-center">
                <span className="text-xs text-muted-foreground">
                  Quality score unchanged
                </span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Value Distributions (Optional, Expandable) */}
      {impactStats.value_distributions &&
        Object.keys(impactStats.value_distributions).length > 0 && (
          <Card className="bg-card">
            <button
              onClick={() => setExpandedDistributions(!expandedDistributions)}
              className="w-full flex items-center justify-between p-6 text-left hover:bg-muted transition-colors"
            >
              <span className="font-semibold text-foreground">
                Value Distribution Changes
              </span>
              <ChevronDown
                className={`w-5 h-5 text-muted-foreground transition-transform ${
                  expandedDistributions ? "rotate-180" : ""
                }`}
              />
            </button>

            {expandedDistributions && (
              <CardContent className="border-t">
                <div className="space-y-6 pt-4">
                  {Object.entries(impactStats.value_distributions).map(
                    ([column, distribution]) => {
                      const beforeEntries = Object.entries(distribution.before);
                      const afterEntries = Object.entries(distribution.after);

                      // Find max count for scaling
                      const allCounts = [
                        ...beforeEntries.map(([, count]) => count),
                        ...afterEntries.map(([, count]) => count),
                      ];
                      const maxCount = Math.max(...allCounts, 1);

                      return (
                        <div key={column} className="space-y-3">
                          <h4 className="text-sm font-semibold text-foreground">
                            {column}
                          </h4>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* Before Distribution */}
                            <div className="space-y-2">
                              <div className="text-xs font-medium text-muted-foreground">
                                Before
                              </div>
                              <div className="space-y-2">
                                {beforeEntries.slice(0, 5).map(([value, count]) => (
                                  <div key={`before-${value}`} className="space-y-1">
                                    <div className="flex items-center justify-between">
                                      <span className="text-xs text-foreground truncate pr-2">
                                        {value}
                                      </span>
                                      <span className="text-xs font-medium text-muted-foreground flex-shrink-0">
                                        {count}
                                      </span>
                                    </div>
                                    <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                                      <div
                                        className="bg-blue-400 h-2 transition-all duration-300"
                                        style={{
                                          width: `${(count / maxCount) * 100}%`,
                                        }}
                                      />
                                    </div>
                                  </div>
                                ))}
                              </div>

                              {beforeEntries.length > 5 && (
                                <div className="text-xs text-muted-foreground pt-1">
                                  +{beforeEntries.length - 5} more values
                                </div>
                              )}
                            </div>

                            {/* After Distribution */}
                            <div className="space-y-2">
                              <div className="text-xs font-medium text-muted-foreground">
                                After
                              </div>
                              <div className="space-y-2">
                                {afterEntries.slice(0, 5).map(([value, count]) => (
                                  <div key={`after-${value}`} className="space-y-1">
                                    <div className="flex items-center justify-between">
                                      <span className="text-xs text-foreground truncate pr-2">
                                        {value}
                                      </span>
                                      <span className="text-xs font-medium text-muted-foreground flex-shrink-0">
                                        {count}
                                      </span>
                                    </div>
                                    <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                                      <div
                                        className="bg-green-400 h-2 transition-all duration-300"
                                        style={{
                                          width: `${(count / maxCount) * 100}%`,
                                        }}
                                      />
                                    </div>
                                  </div>
                                ))}
                              </div>

                              {afterEntries.length > 5 && (
                                <div className="text-xs text-muted-foreground pt-1">
                                  +{afterEntries.length - 5} more values
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    }
                  )}
                </div>
              </CardContent>
            )}
          </Card>
        )}
    </div>
  );
}
