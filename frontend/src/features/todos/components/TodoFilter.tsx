import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTags } from "../api/tags";

export interface TodoFilters {
  keyword?: string;
  status?: "active" | "completed" | "";
  tag_id?: string;
  date_from?: string;
  date_to?: string;
}

interface TodoFilterProps {
  filters: TodoFilters;
  onChange: (filters: TodoFilters) => void;
  onClear: () => void;
}

export function TodoFilter({ filters, onChange, onClear }: TodoFilterProps) {
  const { data: tagsData } = useTags();
  const tags = tagsData?.items ?? [];

  const hasActiveFilters = !!(
    filters.keyword ||
    filters.status ||
    filters.tag_id ||
    filters.date_from ||
    filters.date_to
  );

  return (
    <div className="space-y-3 p-3 bg-muted/30 rounded-lg border">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-muted-foreground">Filters</span>
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs text-muted-foreground hover:text-foreground"
            onClick={onClear}
          >
            <X className="h-3 w-3 mr-1" />
            Clear
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2">
        {/* Keyword search */}
        <div className="col-span-2">
          <Input
            placeholder="Search todos..."
            value={filters.keyword ?? ""}
            onChange={(e) => onChange({ ...filters, keyword: e.target.value || undefined })}
            className="h-8 text-sm"
          />
        </div>

        {/* Status filter */}
        <Select
          value={filters.status ?? ""}
          onValueChange={(val) =>
            onChange({ ...filters, status: val as TodoFilters["status"] || undefined })
          }
        >
          <SelectTrigger className="h-8 text-sm">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
          </SelectContent>
        </Select>

        {/* Tag filter */}
        <Select
          value={filters.tag_id ?? ""}
          onValueChange={(val) =>
            onChange({ ...filters, tag_id: val || undefined })
          }
        >
          <SelectTrigger className="h-8 text-sm">
            <SelectValue placeholder="All tags" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All tags</SelectItem>
            {tags.map((tag) => (
              <SelectItem key={tag.id} value={tag.id}>
                <span className="flex items-center gap-2">
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: tag.color ?? "#6366f1" }}
                  />
                  {tag.name}
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Date from */}
        <Input
          type="date"
          value={filters.date_from ?? ""}
          onChange={(e) =>
            onChange({ ...filters, date_from: e.target.value || undefined })
          }
          className="h-8 text-sm"
          title="From date"
        />

        {/* Date to */}
        <Input
          type="date"
          value={filters.date_to ?? ""}
          onChange={(e) =>
            onChange({ ...filters, date_to: e.target.value || undefined })
          }
          className="h-8 text-sm"
          title="To date"
        />
      </div>
    </div>
  );
}
