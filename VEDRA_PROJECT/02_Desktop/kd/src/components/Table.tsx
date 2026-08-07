import React from 'react';
import type { CSSProperties, ReactNode } from 'react';
import './Table.css';

export interface Column<T> {
  key: string;
  header: ReactNode;
  width?: string;
  align?: 'left' | 'right' | 'center';
  render: (row: T) => ReactNode;
  mono?: boolean;
}

export interface DataTableProps<T> {
  columns: readonly Column<T>[];
  rows: readonly T[];
  onRowClick?: (row: T) => void;
  empty?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export function DataTable<T>({
  columns,
  rows,
  onRowClick,
  empty,
  className,
  style,
}: DataTableProps<T>): React.JSX.Element {
  const rootClasses = ['k-table-root', className].filter(Boolean).join(' ');

  return (
    <div className={rootClasses} style={style}>
      <table className="k-table">
        <colgroup>
          {columns.map((col) => (
            <col
              key={col.key}
              style={col.width !== undefined ? { width: col.width } : undefined}
            />
          ))}
        </colgroup>
        <thead className="k-table__head">
          <tr>
            {columns.map((col) => {
              const alignClass =
                col.align === 'right'
                  ? 'k-table__th--right'
                  : col.align === 'center'
                  ? 'k-table__th--center'
                  : '';
              return (
                <th
                  key={col.key}
                  className={['k-table__th', alignClass]
                    .filter(Boolean)
                    .join(' ')}
                  scope="col"
                >
                  {col.header}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="k-table__body">
          {rows.length === 0 ? (
            <tr>
              <td
                className="k-table__empty"
                colSpan={columns.length}
              >
                {empty ?? 'No items.'}
              </td>
            </tr>
          ) : (
            rows.map((row, rowIdx) => (
              <tr
                key={rowIdx}
                className={[
                  'k-table__row',
                  onRowClick !== undefined && 'k-table__row--clickable',
                ]
                  .filter(Boolean)
                  .join(' ')}
                onClick={
                  onRowClick !== undefined
                    ? () => onRowClick(row)
                    : undefined
                }
              >
                {columns.map((col) => {
                  const alignClass =
                    col.align === 'right'
                      ? 'k-table__td--right'
                      : col.align === 'center'
                      ? 'k-table__td--center'
                      : '';
                  const monoClass =
                    col.mono === true ? 'k-table__td--mono' : '';
                  return (
                    <td
                      key={col.key}
                      className={[
                        'k-table__td',
                        alignClass,
                        monoClass,
                      ]
                        .filter(Boolean)
                        .join(' ')}
                    >
                      {col.render(row)}
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
