import csv
import io


class CursorFormatter(object):

    def __init__(self, cursor, **kwargs):
        self.cursor = cursor
        self.init(**kwargs)

    def init(self):
        pass

    @property
    def column_names(self):
        return [c[0] for c in self.cursor.description]

    @property
    def column_formats(self):
        return [c[1] for c in self.cursor.description]

    def dump(self):
        try:
            data = list(self.cursor.fetchall())
            out = self.format_dump(data)
        finally:
            self.cursor.close()
        return out

    def stream(self, batch=None):
        try:
            column_names = self.column_names
            column_formats = self.column_formats

            if batch is not None:
                while True:
                    b = self.cursor.fetchmany(batch)
                    if len(b) == 0:
                        return
                    yield self.format_dump(b)
            else:
                for row in self.cursor:
                    yield self.format_row(row)
        finally:
            self.cursor.close()

    def format_dump(self, data):
        raise NotImplementedError("{} does not support formatting dumped data.".format(self.__class__.__name__))

    def format_row(self, row):
        raise NotImplementedError("{} does not support formatting streaming data.".format(self.__class__.__name__))


class PandasCursorFormatter(CursorFormatter):

    def init(self, index_fields=None, date_fields=None):
        self.index_fields = index_fields
        self.date_fields = date_fields

    def format_dump(self, data):
        import pandas as pd

        df = pd.DataFrame(data=data, columns=self.column_names)

        if self.date_fields is not None:
            try:
                df = pandas.io.sql._parse_date_columns(df, self.date_fields)
            except Exception as e:
                logger.warning('Unable to parse date columns. Perhaps your version of pandas is outdated.'
                               'Original error message was: {}: {}'.format(e.__class__.__name__, str(e)))

        if self.index_fields is not None:
            df.set_index(self.index_fields, inplace=True)

        return df

    def format_row(self, row):
        import pandas as pd

        # TODO: Handle parsing of date fields

        return pd.Series(row, index=self.column_names)


class DictCursorFormatter(CursorFormatter):

    def format_dump(self, data):
        return [self.format_row(row) for row in data]

    def format_row(self, row):
        return dict(zip(self.column_names, row))


class TupleCursorFormatter(CursorFormatter):

    def format_dump(self, data):
        return [self.format_row(row) for row in self.data]

    def format_row(self, row):
        return row


class CsvCursorFormatter(CursorFormatter):

    # TODO: Add support for outputting headers

    FORMAT_PARAMS = {
        'delimiter': ',',
        'doublequote': False,
        'escapechar': '\\',
        'lineterminator': '\r\n',
        'quotechar': '"',
        'quoting': csv.QUOTE_MINIMAL
    }

    def init(self):
        self.output = io.StringIO()
        self.writer = csv.writer(self.output, **self.FORMAT_PARAMS)

    def format_dump(self, data):
        try:
            self.writer.writerows(data)
            return self.output.getvalue()
        finally:
            self.output.truncate(0)

    def format_row(self, row):
        try:
            self.writer.writerow(row)
            return self.output.getvalue()
        finally:
            self.output.truncate(0)


class HiveCursorFormatter(CsvCursorFormatter):

    # TODO: Handle NULL -> \0

    FORMAT_PARAMS = {
        'delimiter': '\t',
        'doublequote': False,
        'escapechar': None,
        'lineterminator': '\n',
        'quotechar': '',
        'quoting': csv.QUOTE_NONE
    }
